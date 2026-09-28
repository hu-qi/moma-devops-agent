"""Smoke test for persistent delivery intent, execution leases, and deduplication of external side-effects."""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    DeliveryVerifier,
    ExecutionResult,
    TaskExecutor,
    VerificationResult,
)
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CommentSubjectKind,
    CommentSubjectRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.state import IntentStatus, LeaseAcquisitionError
from devopspilot.orchestration.delivery_loop import DeliveryLoop
from devopspilot.orchestration.service import DeliveryOrchestrator
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore

REPO = RepositoryRef(provider_id="mock", repository_id="repo-1", full_name="org/repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="issue-42", title="fix bug")


class CountingSCM:
    def __init__(self) -> None:
        self.create_pr_calls = 0
        self.comment_calls = 0

    async def get_repository(self, repo_id: str) -> RepositoryRef:
        return REPO

    async def get_work_item(self, repo: RepositoryRef, item_id: str) -> WorkItemRef:
        return WORK_ITEM

    async def create_change_request(self, repo: RepositoryRef, *, title: str, body: str, source_branch: str, target_branch: str) -> ChangeRequestRef:
        self.create_pr_calls += 1
        return ChangeRequestRef(
            repository=repo,
            change_id=f"pr-{self.create_pr_calls}",
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            state="open",
        )

    async def add_comment(self, subject: CommentSubjectRef, *, body: str) -> None:
        self.comment_calls += 1


class CountingExecutor:
    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        self.execute_calls += 1
        return ExecutionResult(
            source_branch=f"fix-{self.execute_calls}",
            commit_sha="c12345",
            summary="executed",
            published=True,
        )


class DummyCI:
    pass


class DummyVerifier:
    async def verify(self, state: DeliveryState) -> VerificationResult:
        return VerificationResult(accepted=True, summary="ok")


async def test_deduplication_and_zero_duplicate_side_effects() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_lease_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)
        scm = CountingSCM()
        executor = CountingExecutor()
        loop = DeliveryLoop(scm=scm, ci=DummyCI(), executor=executor, verifier=DummyVerifier())  # type: ignore[arg-type]
        orchestrator = DeliveryOrchestrator(loop=loop, store=store)

        # 1. First execution
        res1 = await orchestrator.start(
            delivery_id="deliv-001",
            repository_id="repo-1",
            work_item_id="issue-42",
            target_branch="main",
        )
        assert res1.delivery_id == "deliv-001"
        assert res1.state.phase is DeliveryPhase.CHANGE_OPENED
        assert executor.execute_calls == 1
        assert scm.create_pr_calls == 1
        assert scm.comment_calls == 1

        # 2. Duplicate start request for the SAME task
        res2 = await orchestrator.start(
            delivery_id="deliv-002",  # Different caller delivery_id, but same repository+work_item+target_branch
            repository_id="repo-1",
            work_item_id="issue-42",
            target_branch="main",
        )
        # Should return the existing delivery state and PREVENT all duplicate side effects!
        assert res2.delivery_id == "deliv-001"
        assert res2.state.phase is DeliveryPhase.CHANGE_OPENED
        assert executor.execute_calls == 1, "Executor should NOT have been called again"
        assert scm.create_pr_calls == 1, "Duplicate PR should NOT have been created"
        assert scm.comment_calls == 1, "Duplicate comment should NOT have been posted"
        print("DEDUP_ZERO_SECONDARY_SIDE_EFFECTS_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def test_concurrent_worker_lease_race() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_race_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)

        dedup_key = "repo-1:issue-99:main"

        # Worker 1 and Worker 2 try to acquire lease simultaneously
        r1, r2 = await asyncio.gather(
            store.acquire_lease(dedup_key, "deliv-101", owner="worker-1", ttl_seconds=60.0),
            store.acquire_lease(dedup_key, "deliv-102", owner="worker-2", ttl_seconds=60.0),
        )

        # Exactly one must win the lease
        assert (r1.acquired and not r2.acquired) or (r2.acquired and not r1.acquired)
        winner = r1 if r1.acquired else r2
        loser = r2 if r1.acquired else r1
        assert winner.status == IntentStatus.ACQUIRED
        assert loser.status == IntentStatus.RUNNING
        assert loser.delivery_id == winner.delivery_id
        print("CONCURRENT_WORKER_LEASE_RACE_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def test_expired_lease_takeover() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_takeover_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)

        dedup_key = "repo-1:issue-crash:main"

        # Worker 1 acquires with very short TTL
        r1 = await store.acquire_lease(dedup_key, "deliv-crash", owner="worker-1", ttl_seconds=0.1)
        assert r1.acquired is True

        # Wait for lease expiration
        await asyncio.sleep(0.2)

        # Worker 2 should be able to take over the expired lease
        r2 = await store.acquire_lease(dedup_key, "deliv-crash", owner="worker-2", ttl_seconds=60.0)
        assert r2.acquired is True
        assert "taken over" in r2.message
        print("EXPIRED_LEASE_TAKEOVER_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def main() -> None:
    await test_deduplication_and_zero_duplicate_side_effects()
    await test_concurrent_worker_lease_race()
    await test_expired_lease_takeover()
    print("ALL DURABLE INTENT LEASE SMOKE TESTS PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
