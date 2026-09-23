"""Restart-safe orchestration smoke for DeliveryOrchestrator."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import AsyncIterator

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
from devopspilot.orchestration import DeliveryLoop, DeliveryOrchestrator
from devopspilot.persistence import SQLiteDeliveryStateStore


class SCM:
    provider_id = "fake"

    async def capabilities(self):
        return frozenset({SCMCapability.ISSUES, SCMCapability.CHANGE_REQUESTS})

    async def normalize_webhook(self, *, headers, body) -> SCMEvent:
        raise NotImplementedError

    async def get_repository(self, repository_id):
        return RepositoryRef("fake", repository_id, repository_id, "main")

    async def get_work_item(self, repository, item_id):
        return WorkItemRef(repository, item_id, "Fix delivery")

    async def get_change_request(self, repository, change_id):
        return ChangeRequestRef(
            repository, change_id, "Fix delivery", "fix/7", "main", "open"
        )

    async def create_change_request(
        self, repository, *, title, body, source_branch, target_branch,
    ):
        return ChangeRequestRef(
            repository, "9", title, source_branch, target_branch, "open"
        )

    async def add_comment(self, subject: CommentSubjectRef, *, body: str):
        return None

    async def submit_review(
        self, repository, *, change_id, state: ReviewState, body,
    ) -> ReviewRef:
        return ReviewRef(repository, change_id, "r1", state, body)


class Executor:
    async def execute(self, task: DeliveryTask):
        return ExecutionResult(
            source_branch="fix/7",
            commit_sha="deadbeef",
            summary="fixed",
            published=True,
        )


class CI:
    provider_id = "fake-ci"

    def __init__(self):
        self.ready = False

    async def capabilities(self):
        return frozenset({CICapability.RUNS, CICapability.LOGS})

    async def get_run(self, repository, run_id):
        raise NotImplementedError

    async def list_runs(
        self, repository, *, commit_sha=None, ref=None, status=None, limit=20,
    ):
        if not self.ready:
            return ()
        return (
            CIRunRef(
                provider_id=self.provider_id,
                run_id="100",
                repository=repository,
                status="completed",
                conclusion="success",
                commit_sha=commit_sha,
            ),
        )

    async def stream_logs(self, run) -> AsyncIterator[CIJobLog]:
        if False:
            yield

    async def retry_failed(self, run):
        raise NotImplementedError

    async def trigger(self, repository, *, ref, workflow_id=None, inputs=None):
        raise NotImplementedError

    async def cancel(self, run):
        return None

    async def list_artifacts(self, run) -> tuple[CIArtifactRef, ...]:
        return ()


class Verifier:
    async def verify(self, state: DeliveryState):
        return VerificationResult(
            accepted=state.phase is DeliveryPhase.CI_PASSED,
            summary="accepted" if state.phase is DeliveryPhase.CI_PASSED else "rejected",
        )


async def main() -> None:
    db = Path(tempfile.mkdtemp()) / "delivery.db"
    ci = CI()
    store = SQLiteDeliveryStateStore(db)

    loop = DeliveryLoop(
        scm=SCM(),
        ci=ci,
        executor=Executor(),
        verifier=Verifier(),
    )
    service = DeliveryOrchestrator(loop=loop, store=store)

    started = await service.start(
        "delivery-7",
        repository_id="acme/demo",
        work_item_id="7",
    )
    assert started.state.phase is DeliveryPhase.CHANGE_OPENED
    assert started.version == 1

    pending = await service.reconcile_ci("delivery-7")
    assert pending.state.phase is DeliveryPhase.CI_PENDING
    assert pending.version == 2

    # Simulate process restart: construct a new store/service instance.
    ci.ready = True
    restarted_store = SQLiteDeliveryStateStore(db)
    restarted = DeliveryOrchestrator(
        loop=DeliveryLoop(
            scm=SCM(),
            ci=ci,
            executor=Executor(),
            verifier=Verifier(),
        ),
        store=restarted_store,
    )

    passed = await restarted.reconcile_ci("delivery-7")
    assert passed.state.phase is DeliveryPhase.CI_PASSED
    assert passed.version == 3

    verified = await restarted.verify("delivery-7")
    assert verified.state.phase is DeliveryPhase.VERIFIED
    assert verified.version == 4

    final = await restarted.get("delivery-7")
    assert final is not None
    assert final.state.phase is DeliveryPhase.VERIFIED

    print("DURABLE_DELIVERY_START_OK")
    print("DURABLE_CI_RECONCILE_OK")
    print("PROCESS_RESTART_RECOVERY_OK")
    print("OPTIMISTIC_STATE_VERSION_OK")


if __name__ == "__main__":
    asyncio.run(main())
