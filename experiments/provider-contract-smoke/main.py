"""Smoke-test the provider-neutral SCM/CI contracts without external credentials."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Mapping

from devopspilot.contracts.providers import (
    CIArtifactRef,
    CICapability,
    CIJobLog,
    CIProvider,
    CIRunRef,
    ChangeRequestRef,
    CommentSubjectKind,
    CommentSubjectRef,
    RepositoryRef,
    ReviewRef,
    ReviewState,
    SCMCapability,
    SCMEvent,
    SCMProvider,
    WorkItemRef,
)


class FakeSCMProvider:
    provider_id = "fake-scm"

    async def capabilities(self) -> frozenset[SCMCapability]:
        return frozenset({
            SCMCapability.ISSUES,
            SCMCapability.CHANGE_REQUESTS,
            SCMCapability.REVIEWS,
            SCMCapability.WEBHOOKS,
        })

    async def normalize_webhook(
        self, *, headers: Mapping[str, str], body: bytes,
    ) -> SCMEvent:
        payload = json.loads(body or b"{}")
        repo = await self.get_repository("demo/repo")
        return SCMEvent(
            provider_id=self.provider_id,
            event_id=headers.get("x-event-id", "event-1"),
            event_type=str(payload.get("type", "issue.open")),
            repository=repo,
            payload=payload,
        )

    async def get_repository(self, repository_id: str) -> RepositoryRef:
        return RepositoryRef(
            provider_id=self.provider_id,
            repository_id=repository_id,
            full_name=repository_id,
            default_branch="main",
        )

    async def get_work_item(
        self, repository: RepositoryRef, item_id: str,
    ) -> WorkItemRef:
        return WorkItemRef(repository=repository, item_id=item_id, title="Demo issue")

    async def get_change_request(
        self, repository: RepositoryRef, change_id: str,
    ) -> ChangeRequestRef:
        return ChangeRequestRef(
            repository=repository,
            change_id=change_id,
            title="Demo change",
            source_branch="fix/demo",
            target_branch="main",
            state="open",
        )

    async def create_change_request(
        self, repository: RepositoryRef, *, title: str, body: str,
        source_branch: str, target_branch: str,
    ) -> ChangeRequestRef:
        return ChangeRequestRef(
            repository=repository,
            change_id="1",
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            state="open",
        )

    async def add_comment(self, subject: CommentSubjectRef, *, body: str) -> None:
        assert subject.kind in {
            CommentSubjectKind.WORK_ITEM,
            CommentSubjectKind.CHANGE_REQUEST,
        }

    async def submit_review(
        self, repository: RepositoryRef, *, change_id: str,
        state: ReviewState, body: str,
    ) -> ReviewRef:
        return ReviewRef(
            repository=repository,
            change_id=change_id,
            review_id="review-1",
            state=state,
            body=body,
        )


class FakeCIProvider:
    provider_id = "fake-ci"

    async def capabilities(self) -> frozenset[CICapability]:
        return frozenset(CICapability)

    async def get_run(
        self, repository: RepositoryRef, run_id: str,
    ) -> CIRunRef:
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=run_id,
            repository=repository,
            status="completed",
            conclusion="failure",
            commit_sha="deadbeef",
        )

    async def list_runs(
        self, repository: RepositoryRef, *, commit_sha: str | None = None,
        ref: str | None = None, status: str | None = None, limit: int = 20,
    ) -> tuple[CIRunRef, ...]:
        return (
            CIRunRef(
                provider_id=self.provider_id,
                run_id="run-1",
                repository=repository,
                status=status or "completed",
                conclusion="failure",
                commit_sha=commit_sha or "deadbeef",
            ),
        )

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        yield CIJobLog(run=run, job_id="job-1", job_name="test", content="failed")

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        return CIRunRef(
            provider_id=run.provider_id,
            run_id=f"{run.run_id}-retry",
            repository=run.repository,
            status="queued",
            commit_sha=run.commit_sha,
        )

    async def trigger(
        self, repository: RepositoryRef, *, ref: str,
        workflow_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> CIRunRef:
        return CIRunRef(
            provider_id=self.provider_id,
            run_id="triggered-1",
            repository=repository,
            status="queued",
        )

    async def cancel(self, run: CIRunRef) -> None:
        return None

    async def list_artifacts(self, run: CIRunRef) -> tuple[CIArtifactRef, ...]:
        return (CIArtifactRef(run=run, artifact_id="artifact-1", name="logs"),)


async def main() -> None:
    scm = FakeSCMProvider()
    ci = FakeCIProvider()

    assert isinstance(scm, SCMProvider)
    assert isinstance(ci, CIProvider)

    repo = await scm.get_repository("demo/repo")
    event = await scm.normalize_webhook(
        headers={"x-event-id": "evt-42"},
        body=b'{"type":"issue.open"}',
    )
    change = await scm.create_change_request(
        repo,
        title="Fix demo",
        body="",
        source_branch="fix/demo",
        target_branch="main",
    )
    await scm.add_comment(
        CommentSubjectRef(
            repository=repo,
            subject_id=change.change_id,
            kind=CommentSubjectKind.CHANGE_REQUEST,
        ),
        body="Delivery update",
    )
    review = await scm.submit_review(
        repo,
        change_id=change.change_id,
        state=ReviewState.APPROVE,
        body="Looks good",
    )

    discovered = await ci.list_runs(repo, commit_sha="deadbeef", ref="fix/demo")
    run = discovered[0]
    logs = [log async for log in ci.stream_logs(run)]
    retry = await ci.retry_failed(run)

    assert event.event_id == "evt-42"
    assert review.state is ReviewState.APPROVE
    assert run.commit_sha == "deadbeef"
    assert logs[0].content == "failed"
    assert retry.status == "queued"
    assert CICapability.LOGS in await ci.capabilities()

    partial_ci = frozenset({CICapability.RUNS})
    assert CICapability.LOGS not in partial_ci

    print("SCM_PROVIDER_CONTRACT_OK")
    print("CI_PROVIDER_CONTRACT_OK")
    print("CI_RUN_DISCOVERY_OK")


if __name__ == "__main__":
    asyncio.run(main())
