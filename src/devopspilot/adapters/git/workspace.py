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
