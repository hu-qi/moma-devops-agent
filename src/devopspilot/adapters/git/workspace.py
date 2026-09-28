"""Git worktree-backed execution workspace provider."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.execution import ExecutionWorkspace


async def _git(*args: str, cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({process.returncode}): "
            f"{stderr.decode('utf-8', errors='replace')}"
        )
    return stdout.decode("utf-8", errors="replace").strip()


def _safe_ref(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._/-]+", "-", value.strip())
    value = re.sub(r"/+", "/", value).strip("/.-")
    if not value:
        raise ValueError("Cannot derive a Git branch from an empty work item id")
    return value


class GitWorktreeWorkspaceProvider:
    """Create one isolated Git worktree and source branch per delivery task."""

    def __init__(
        self,
        repository_path: str | Path,
        *,
        temp_root: str | Path | None = None,
        branch_prefix: str = "devopspilot",
    ) -> None:
        self._repository_path = Path(repository_path).resolve()
        self._temp_root = Path(temp_root).resolve() if temp_root else None
        self._branch_prefix = branch_prefix.strip("/")

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        if not self._repository_path.is_dir():
            raise FileNotFoundError(
                f"Git repository path not found: {self._repository_path}"
            )

        source_branch = task.metadata.get("source_branch") or (
            f"{self._branch_prefix}/{_safe_ref(task.work_item.item_id)}"
        )
        source_branch = _safe_ref(source_branch)

        base_commit = await _git(
            "rev-parse",
            task.target_branch,
            cwd=self._repository_path,
        )

        parent = str(self._temp_root) if self._temp_root else None
        path = Path(tempfile.mkdtemp(
            prefix="devopspilot_worktree_",
            dir=parent,
        )).resolve()
        # git worktree add requires the target path not to pre-exist.
        path.rmdir()

        try:
            await _git(
                "worktree",
                "add",
                "-b",
                source_branch,
                str(path),
                base_commit,
                cwd=self._repository_path,
            )
        except Exception:
            if path.exists():
                path.rmdir()
            raise

        return ExecutionWorkspace(
            path=path,
            source_branch=source_branch,
            base_commit=base_commit,
            metadata={
                **dict(task.metadata),
                "workspace_kind": "git-worktree",
                "source_repository_path": str(self._repository_path),
            },
        )

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        if workspace.path.exists():
            await _git(
                "worktree",
                "remove",
                "--force",
                str(workspace.path),
                cwd=self._repository_path,
            )

        # Remove only the local execution branch. A published remote branch is
        # unaffected.
        process = await asyncio.create_subprocess_exec(
            "git",
            "branch",
            "-D",
            workspace.source_branch,
            cwd=str(self._repository_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        await _git("worktree", "prune", cwd=self._repository_path)


class AutoCloningWorktreeWorkspaceProvider:
    """Prepare a Git worktree, automatically cloning or updating the base repo if needed."""

    def __init__(
        self,
        repository_id: str,
        clone_url: str,
        *,
        cache_dir: str | Path | None = None,
        branch_prefix: str = "devopspilot",
        clone_auth_args: tuple[str, ...] | list[str] = (),
    ) -> None:
        self._repository_id = repository_id
        self._clone_url = clone_url
        # C06: per-invocation auth via `-c http.extraHeader=...`; never persisted in URL
        self._clone_auth_args = tuple(clone_auth_args)
        self._cache_dir = Path(cache_dir).resolve() if cache_dir else (Path.home() / ".devopspilot" / "repos")
        self._branch_prefix = branch_prefix
        self._inner_provider: GitWorktreeWorkspaceProvider | None = None

    async def _resolve_repo_path(self, target_branch: str) -> Path:
        # 1. Check if current working directory is the repository
        cwd = Path.cwd()
        if (cwd / ".git").exists():
            try:
                origin_url = await _git("remote", "get-url", "origin", cwd=cwd)
                if self._repository_id.lower() in origin_url.lower():
                    return cwd
            except Exception:
                pass

        # 2. Check or create in cache_dir
        repo_dir = self._cache_dir / self._repository_id
        if not repo_dir.exists():
            repo_dir.parent.mkdir(parents=True, exist_ok=True)
            print(f"[Workspace] Cloning repository {self._repository_id} into {repo_dir}...")
            await _git("clone", *self._clone_auth_args, self._clone_url, str(repo_dir), cwd=repo_dir.parent)
        else:
            # Fetch latest (auth via extraHeader args, URL stays credential-free)
            try:
                await _git("fetch", *self._clone_auth_args, "origin", cwd=repo_dir)
            except Exception as exc:
                print(f"[Workspace] Fetch origin warning: {exc}")

        # Ensure target_branch exists locally
        try:
            await _git("rev-parse", "--verify", target_branch, cwd=repo_dir)
        except Exception:
            # Try to checkout or create branch tracking origin
            try:
                await _git("branch", target_branch, f"origin/{target_branch}", cwd=repo_dir)
            except Exception:
                pass

        return repo_dir

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        repo_path = await self._resolve_repo_path(task.target_branch)
        self._inner_provider = GitWorktreeWorkspaceProvider(
            repo_path,
            branch_prefix=self._branch_prefix,
        )
        return await self._inner_provider.prepare(task)

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        if self._inner_provider:
            await self._inner_provider.cleanup(workspace)
