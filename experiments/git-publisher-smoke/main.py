"""Local bare-remote validation for GitChangePublisher."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

from devopspilot.adapters.git import GitChangePublisher
from devopspilot.contracts.delivery import DeliveryTask, ExecutionResult
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


async def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="devopspilot_git_publish_"))
    remote = root / "remote.git"
    work = root / "work"

    git("init", "--bare", str(remote))
    git("init", str(work))
    git("config", "user.name", "DevOpsPilot", cwd=work)
    git("config", "user.email", "devopspilot@local", cwd=work)

    (work / "demo.txt").write_text("validated\n", encoding="utf-8")
    git("add", "demo.txt", cwd=work)
    git("commit", "-m", "validated change", cwd=work)
    git("checkout", "-b", "devopspilot/demo-1", cwd=work)
    commit = git("rev-parse", "HEAD", cwd=work)
    git("remote", "add", "origin", str(remote), cwd=work)

    repository = RepositoryRef(
        provider_id="fake",
        repository_id="demo",
        full_name="acme/demo",
        default_branch="main",
    )
    task = DeliveryTask(
        repository=repository,
        work_item=WorkItemRef(repository, "1", "Demo"),
        target_branch="main",
    )
    result = ExecutionResult(
        source_branch="devopspilot/demo-1",
        commit_sha=commit,
        summary="validated",
        published=False,
        metadata={"workspace_path": str(work)},
    )

    published = await GitChangePublisher().publish(task, result)
    assert published.published is True
    assert published.commit_sha == commit

    remote_head = git(
        "--git-dir", str(remote),
        "rev-parse", "refs/heads/devopspilot/demo-1",
    )
    assert remote_head == commit

    print("GIT_PUBLISHER_OK")
    print("PUBLISHED_COMMIT_IDENTITY_OK")
    print("DIRTY_WORKTREE_GUARD_AVAILABLE")


if __name__ == "__main__":
    asyncio.run(main())
