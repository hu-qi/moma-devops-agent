"""End-to-end credential-free smoke for the provider-neutral DeliveryLoop."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Mapping

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
    CommentSubjectKind,
    CommentSubjectRef,
    RepositoryRef,
    ReviewRef,
    ReviewState,
    SCMCapability,
    SCMEvent,
    WorkItemRef,
)
from devopspilot.orchestration import DeliveryLoop


class FakeSCM:
    provider_id = "fake-scm"

    def __init__(self) -> None:
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
        return RepositoryRef(
            provider_id=self.provider_id,
            repository_id=repository_id,
            full_name=repository_id,
            default_branch="main",
        )

    async def get_work_item(self, repository: RepositoryRef, item_id: str) -> WorkItemRef:
        return WorkItemRef(
            repository=repository,
            item_id=item_id,
            title="Repair CI regression",
            body="Tests fail after the latest change.",
            labels=("bug", "ci"),
        )

    async def get_change_request(self, repository, change_id):
        return ChangeRequestRef(
            repository=repository,
            change_id=change_id,
            title="Repair CI regression",
            source_branch="devopspilot/fix-7",
            target_branch="main",
            state="open",
        )

    async def create_change_request(
        self, repository, *, title, body, source_branch, target_branch,
    ) -> ChangeRequestRef:
        assert "DevOpsPilot Delivery" in body
        return ChangeRequestRef(
            repository=repository,
            change_id="9",
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            state="open",
        )

    async def add_comment(self, subject: CommentSubjectRef, *, body: str) -> None:
        self.comments.append((subject, body))

    async def submit_review(
        self, repository, *, change_id, state: ReviewState, body,
    ) -> ReviewRef:
        return ReviewRef(
            repository=repository,
            change_id=change_id,
            review_id="r1",
            state=state,
            body=body,
        )


class FakeExecutor:
    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        assert task.work_item.item_id == "7"
        return ExecutionResult(
            source_branch="devopspilot/fix-7",
            commit_sha="deadbeef",
            summary="Guard missing PORT and add deterministic tests.",
            test_summary="3 local tests passed.",
            published=True,
        )


class FakeCI:
    provider_id = "fake-ci"

    def __init__(self) -> None:
        self.mode = "pending"

    async def capabilities(self):
        return frozenset({
            CICapability.RUNS,
            CICapability.JOBS,
            CICapability.LOGS,
        })

    async def get_run(self, repository, run_id):
        raise NotImplementedError

    async def list_runs(
        self, repository, *, commit_sha=None, ref=None, status=None, limit=20,
    ):
        assert commit_sha == "deadbeef"
        assert ref == "devopspilot/fix-7"
        if self.mode == "pending":
            return ()
        conclusion = "failure" if self.mode == "failed" else "success"
        return (
            CIRunRef(
                provider_id=self.provider_id,
                run_id="100",
                repository=repository,
                status="completed",
                conclusion=conclusion,
                commit_sha=commit_sha,
            ),
        )

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        yield CIJobLog(
            run=run,
            job_id="test",
            job_name="pytest",
            content="AssertionError: expected fallback port",
        )

    async def retry_failed(self, run):
        raise NotImplementedError

    async def trigger(self, repository, *, ref, workflow_id=None, inputs=None):
        raise NotImplementedError

    async def cancel(self, run):
        return None

    async def list_artifacts(self, run) -> tuple[CIArtifactRef, ...]:
        return ()


class FakeVerifier:
    async def verify(self, state: DeliveryState) -> VerificationResult:
        if state.phase is DeliveryPhase.CI_PASSED:
            return VerificationResult(
                accepted=True,
                summary="CI passed; delivery accepted.",
                evidence=(state.ci_run.run_id if state.ci_run else "",),
            )
        return VerificationResult(
            accepted=False,
            summary="CI failed; remediation required.",
            evidence=tuple(log.job_name for log in state.ci_logs),
        )


async def main() -> None:
    scm = FakeSCM()
    ci = FakeCI()
    loop = DeliveryLoop(
        scm=scm,
        ci=ci,
        executor=FakeExecutor(),
        verifier=FakeVerifier(),
    )

    opened = await loop.start(repository_id="acme/demo", work_item_id="7")
    assert opened.phase is DeliveryPhase.CHANGE_OPENED
    assert opened.change_request.change_id == "9"
    assert scm.comments[0][0].kind is CommentSubjectKind.WORK_ITEM

    pending = await loop.reconcile_ci(opened)
    assert pending.phase is DeliveryPhase.CI_PENDING

    ci.mode = "failed"
    failed = await loop.reconcile_ci(pending)
    assert failed.phase is DeliveryPhase.CI_FAILED
    assert "AssertionError" in failed.ci_logs[0].content

    rejected = await loop.verify(failed)
    assert rejected.phase is DeliveryPhase.REJECTED

    # A later event can reconcile the same delivery again without a hidden
    # background process. This is the intended event-driven recovery model.
    ci.mode = "passed"
    passed = await loop.reconcile_ci(failed)
    assert passed.phase is DeliveryPhase.CI_PASSED

    verified = await loop.verify(passed)
    assert verified.phase is DeliveryPhase.VERIFIED

    print("DELIVERY_LOOP_START_OK")
    print("DELIVERY_LOOP_CI_PENDING_OK")
    print("DELIVERY_LOOP_FAILURE_EVIDENCE_OK")
    print("DELIVERY_LOOP_RESUME_OK")
    print("DELIVERY_LOOP_VERIFIED_OK")


if __name__ == "__main__":
    asyncio.run(main())
