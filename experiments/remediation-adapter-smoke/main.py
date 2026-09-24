"""Smoke coverage for same-branch remediation adapters."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

from devopspilot.adapters.git.existing_branch import GitExistingBranchWorkspaceProvider
from devopspilot.adapters.openjiuwen.remediation import OpenJiuwenRemediationExecutor
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import CIRunRef, RepositoryRef, WorkItemRef
from devopspilot.contracts.remediation import CIFailureAnalysis, CIFailureKind


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


class CapturingExecutor:
    def __init__(self) -> None:
        self.task = None

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        self.task = task
        return ExecutionResult(
            source_branch=task.metadata["source_branch"],
            commit_sha="repair-commit",
            summary="repair",
            published=True,
            test_summary="verification passed",
        )


async def workspace_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp_value:
        tmp = Path(tmp_value)
        remote = tmp / "remote.git"
        repo = tmp / "repo"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True)
        subprocess.run(["git", "init", str(repo)], check=True)
        git(repo, "config", "user.name", "DevOpsPilot")
        git(repo, "config", "user.email", "devopspilot@local")
        (repo / "app.py").write_text("value = 'base'\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-m", "base")
        git(repo, "branch", "-M", "main")
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "-u", "origin", "main")
        git(repo, "checkout", "-b", "devopspilot/live-fix")
        (repo / "app.py").write_text("value = 'candidate'\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-m", "candidate")
        git(repo, "push", "origin", "devopspilot/live-fix")
        candidate_sha = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "main")

        repository = RepositoryRef("git", "repo-1", "acme/demo", "main")
        work = WorkItemRef(repository, "7", "repair")
        task = DeliveryTask(
            repository,
            work,
            "main",
            metadata={
                "source_branch": "devopspilot/live-fix",
                "execution_id": "remediation-1",
            },
        )
        provider = GitExistingBranchWorkspaceProvider(repo)
        workspace = await provider.prepare(task)
        try:
            assert workspace.source_branch == "devopspilot/live-fix"
            assert workspace.base_commit == candidate_sha
            assert git(workspace.path, "rev-parse", "HEAD") == candidate_sha
            assert workspace.metadata["local_execution_branch"].startswith(
                "devopspilot-local/"
            )
        finally:
            await provider.cleanup(workspace)


async def remediation_contract() -> None:
    repository = RepositoryRef("github", "repo-1", "acme/demo", "main")
    work = WorkItemRef(repository, "7", "repair", "Original issue body")
    task = DeliveryTask(
        repository,
        work,
        "main",
        metadata={
            "allowed_paths": "app.py",
            "test_command": "python test_app.py",
        },
    )
    run = CIRunRef(
        "github-actions",
        "100",
        repository,
        "completed",
        "failure",
        "bad-commit",
    )
    state = DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=ExecutionResult(
            "devopspilot/live-fix",
            "bad-commit",
            "candidate",
            True,
        ),
        ci_run=run,
    )
    inner = CapturingExecutor()
    adapter = OpenJiuwenRemediationExecutor(inner)
    result = await adapter.remediate(
        state,
        CIFailureAnalysis(
            CIFailureKind.CODE,
            "tests failed",
            ("pytest: AssertionError: expected fixed",),
        ),
        attempt=1,
    )
    assert result.source_branch == "devopspilot/live-fix"
    assert inner.task.metadata["source_branch"] == "devopspilot/live-fix"
    assert inner.task.metadata["execution_id"] == "remediation-1"
    assert "AssertionError: expected fixed" in inner.task.work_item.body
    assert inner.task.metadata["allowed_paths"] == "app.py"


async def main() -> None:
    await workspace_contract()
    await remediation_contract()
    print("REMEDIATION_EXISTING_BRANCH_WORKSPACE_OK")
    print("REMEDIATION_AGENT_CONTEXT_OK")
    print("REMEDIATION_SOURCE_BRANCH_IDENTITY_OK")


if __name__ == "__main__":
    asyncio.run(main())
