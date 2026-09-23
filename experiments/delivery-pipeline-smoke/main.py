"""Full provider-neutral delivery pipeline integration smoke.

This test joins:
DeliveryLoop
  -> PublishingTaskExecutor
  -> local TaskExecutor
  -> GitChangePublisher
  -> SCMProvider
  -> CIProvider
  -> DeliveryVerifier

It uses a real local Git repository + bare remote, while SCM/CI API effects are
deterministic fakes. This isolates product orchestration from network/provider
credentials before the live GitHub E2E gate.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, AsyncIterator, Mapping

from devopspilot.adapters.git import GitChangePublisher
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
    VerificationResult,
)
from devopspilot.contracts.providers import (
    CIArtifactRef,
    CICapability,
    CIJobLog,
    CIRunRef,
    ChangeRequestRef,
    CommentSubjectRef,
    RepositoryRef,
    ReviewRef,
    ReviewState,
    SCMCapability,
    SCMEvent,
    WorkItemRef,
)
from devopspilot.orchestration import DeliveryLoop, PublishingTaskExecutor


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()


class LocalCommittedExecutor:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        source_branch = f"devopspilot/{task.work_item.item_id}"
        git("checkout", "-b", source_branch, cwd=self.workspace)

        target = self.workspace / "app.py"
        target.write_text(
            "def status():\n    return 'fixed'\n",
            encoding="utf-8",
        )
        git("add", "app.py", cwd=self.workspace)
        git(
            "-c", "user.name=DevOpsPilot",
            "-c", "user.email=devopspilot@local",
            "commit", "-m", "fix: delivery pipeline smoke",
            cwd=self.workspace,
        )
        sha = git("rev-parse", "HEAD", cwd=self.workspace)

        return ExecutionResult(
            source_branch=source_branch,
            commit_sha=sha,
            summary="Deterministic code repair completed.",
            published=False,
            test_summary="local fixture verification passed",
            metadata={"workspace_path": str(self.workspace)},
        )


class FakeSCM:
    provider_id = "integration-scm"

    def __init__(self, repository: RepositoryRef) -> None:
        self.repository = repository
        self.created_change: ChangeRequestRef | None = None
        self.comments: list[tuple[CommentSubjectRef, str]] = []

    async def capabilities(self):
        return frozenset({
            SCMCapability.ISSUES,
            SCMCapability.CHANGE_REQUESTS,
            SCMCapability.REVIEWS,
        })

    async def normalize_webhook(self, *, headers, body) -> SCMEvent:
        raise NotImplementedError

    async def get_repository(self, repository_id: str) -> RepositoryRef:
        assert repository_id == self.repository.repository_id
        return self.repository

    async def get_work_item(
        self, repository: RepositoryRef, item_id: str,
    ) -> WorkItemRef:
        return WorkItemRef(
            repository=repository,
            item_id=item_id,
            title="Repair integration fixture",
            body="Change app.status() from broken to fixed.",
            labels=("integration",),
        )

    async def get_change_request(
        self, repository: RepositoryRef, change_id: str,
    ) -> ChangeRequestRef:
        assert self.created_change is not None
        return self.created_change

    async def create_change_request(
        self,
        repository: RepositoryRef,
        *,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
    ) -> ChangeRequestRef:
        assert "DevOpsPilot Delivery" in body
        change = ChangeRequestRef(
            repository=repository,
            change_id="42",
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            state="open",
            web_url="https://example.invalid/pr/42",
        )
        self.created_change = change
        return change

    async def add_comment(
        self,
        subject: CommentSubjectRef,
        *,
        body: str,
    ) -> None:
        self.comments.append((subject, body))

    async def submit_review(
        self,
        repository: RepositoryRef,
        *,
        change_id: str,
        state: ReviewState,
        body: str,
    ) -> ReviewRef:
        return ReviewRef(
            repository=repository,
            change_id=change_id,
            review_id="review-1",
            state=state,
            body=body,
        )


class FakeCI:
    provider_id = "integration-ci"

    def __init__(self, remote: Path) -> None:
        self.remote = remote

    async def capabilities(self):
        return frozenset({
            CICapability.RUNS,
            CICapability.JOBS,
            CICapability.LOGS,
        })

    async def get_run(
        self, repository: RepositoryRef, run_id: str,
    ) -> CIRunRef:
        raise NotImplementedError

    async def list_runs(
        self,
        repository: RepositoryRef,
        *,
        commit_sha: str | None = None,
        ref: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> tuple[CIRunRef, ...]:
        assert commit_sha
        assert ref
        remote_sha = git(
            "--git-dir", str(self.remote),
            "rev-parse", f"refs/heads/{ref}",
        )
        assert remote_sha == commit_sha
        return (
            CIRunRef(
                provider_id=self.provider_id,
                run_id="ci-42",
                repository=repository,
                status="completed",
                conclusion="success",
                commit_sha=commit_sha,
                web_url="https://example.invalid/ci/42",
            ),
        )

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        yield CIJobLog(
            run=run,
            job_id="test",
            job_name="test",
            content="integration fixture passed",
        )

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        raise NotImplementedError

    async def trigger(
        self,
        repository: RepositoryRef,
        *,
        ref: str,
        workflow_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> CIRunRef:
        raise NotImplementedError

    async def cancel(self, run: CIRunRef) -> None:
        return None

    async def list_artifacts(
        self, run: CIRunRef,
    ) -> tuple[CIArtifactRef, ...]:
        return ()


class GateVerifier:
    async def verify(self, state: DeliveryState) -> VerificationResult:
        accepted = (
            state.phase is DeliveryPhase.CI_PASSED
            and state.ci_run is not None
            and state.ci_run.conclusion == "success"
        )
        return VerificationResult(
            accepted=accepted,
            summary="CI evidence accepted." if accepted else "CI evidence rejected.",
            evidence=(state.ci_run.run_id,) if state.ci_run else (),
        )


async def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="devopspilot_delivery_pipeline_"))
    remote = root / "remote.git"
    workspace = root / "workspace"

    git("init", "--bare", str(remote))
    git("init", str(workspace))
    git("config", "user.name", "DevOpsPilot", cwd=workspace)
    git("config", "user.email", "devopspilot@local", cwd=workspace)
    (workspace / "app.py").write_text(
        "def status():\n    return 'broken'\n",
        encoding="utf-8",
    )
    git("add", "app.py", cwd=workspace)
    git("commit", "-m", "fixture: broken state", cwd=workspace)
    git("branch", "-M", "main", cwd=workspace)
    git("remote", "add", "origin", str(remote), cwd=workspace)
    git("push", "-u", "origin", "main", cwd=workspace)

    repository = RepositoryRef(
        provider_id="integration-scm",
        repository_id="acme/demo",
        full_name="acme/demo",
        default_branch="main",
    )
    scm = FakeSCM(repository)
    ci = FakeCI(remote)
    executor = PublishingTaskExecutor(
        LocalCommittedExecutor(workspace),
        GitChangePublisher(),
    )
    loop = DeliveryLoop(
        scm=scm,
        ci=ci,
        executor=executor,
        verifier=GateVerifier(),
    )

    opened = await loop.start(
        repository_id="acme/demo",
        work_item_id="issue-42",
    )
    assert opened.phase is DeliveryPhase.CHANGE_OPENED
    assert opened.execution is not None
    assert opened.execution.published is True
    assert opened.change_request is not None
    assert opened.change_request.source_branch == "devopspilot/issue-42"

    remote_sha = git(
        "--git-dir", str(remote),
        "rev-parse", "refs/heads/devopspilot/issue-42",
    )
    assert remote_sha == opened.execution.commit_sha

    ci_state = await loop.reconcile_ci(opened)
    assert ci_state.phase is DeliveryPhase.CI_PASSED
    assert ci_state.ci_run is not None
    assert ci_state.ci_run.commit_sha == opened.execution.commit_sha

    verified = await loop.verify(ci_state)
    assert verified.phase is DeliveryPhase.VERIFIED
    assert verified.verification is not None
    assert verified.verification.accepted is True

    assert scm.created_change is not None
    assert scm.comments

    print("DELIVERY_PIPELINE_EXECUTE_OK")
    print("DELIVERY_PIPELINE_PUBLISH_OK")
    print("DELIVERY_PIPELINE_CHANGE_REQUEST_OK")
    print("DELIVERY_PIPELINE_CI_CORRELATION_OK")
    print("DELIVERY_PIPELINE_VERIFIED_OK")
    print(f"DELIVERY_PIPELINE_COMMIT={opened.execution.commit_sha}")


if __name__ == "__main__":
    asyncio.run(main())
