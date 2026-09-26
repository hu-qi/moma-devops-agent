"""Git workspace provider for continuing work on an existing remote branch."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path

from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.execution import ExecutionWorkspace

from .workspace import _git, _safe_ref


def _local_slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return value or "attempt"


class GitExistingBranchWorkspaceProvider:
    """Create an isolated worktree from an already-published remote branch.

    The worktree uses a temporary local branch while ExecutionWorkspace keeps
    source_branch equal to the real remote PR/MR branch. GitChangePublisher can
    therefore push the validated remediation commit back to that same branch.
    """

    def __init__(
        self,
        repository_path: str | Path,
        *,
        remote: str = "origin",
        temp_root: str | Path | None = None,
    ) -> None:
        self._repository_path = Path(repository_path).resolve()
        self._remote = remote
        self._temp_root = Path(temp_root).resolve() if temp_root else None

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        if not self._repository_path.is_dir():
            raise FileNotFoundError(
                f"Git repository path not found: {self._repository_path}"
            )
        source_branch = _safe_ref(task.metadata.get("source_branch", ""))
        if not source_branch:
            raise ValueError(
                "existing-branch workspace requires task metadata source_branch"
            )

        remote_ref = f"refs/remotes/{self._remote}/{source_branch}"
        await _git(
            "fetch",
            self._remote,
            f"refs/heads/{source_branch}:{remote_ref}",
            cwd=self._repository_path,
        )
        base_commit = await _git(
            "rev-parse",
            remote_ref,
            cwd=self._repository_path,
        )

        attempt = _local_slug(task.metadata.get("execution_id", "remediation"))
        local_branch = _safe_ref(
            f"devopspilot-local/{source_branch.replace('/', '-')}-{attempt}"
        )
        parent = str(self._temp_root) if self._temp_root else None
        path = Path(tempfile.mkdtemp(
            prefix="devopspilot_remediation_",
            dir=parent,
        )).resolve()
        path.rmdir()

        try:
            await _git(
                "worktree",
                "add",
                "-b",
                local_branch,
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
                "workspace_kind": "git-existing-branch-worktree",
                "source_repository_path": str(self._repository_path),
                "local_execution_branch": local_branch,
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
        local_branch = workspace.metadata.get(
            "local_execution_branch",
            "",
        ).strip()
        if local_branch:
            process = await asyncio.create_subprocess_exec(
                "git",
                "branch",
                "-D",
                local_branch,
                cwd=str(self._repository_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        await _git("worktree", "prune", cwd=self._repository_path)
