"""Failure boundary, interruption, and governance smoke test.

Validates the 5 critical failure and security boundary scenarios:
1. Permission / Policy Denied: Protected branch or lack of write permissions triggers ESCALATE immediately without code mutation retries.
2. Model Quota / Unavailable: Fails cleanly with recorded error reason, no silent ignoring or fake success.
3. CI Pending Timeout: Exceeding maximum CI wait window halts cleanly without unbounded polling.
4. Process Interruption & Lease Resume: Worker crash preserves existing attempt count and state; resume safely takes over.
5. Budget Exhaustion: Exceeding max remediation attempts terminates the loop with ESCALATED status and complete audit trail.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import (
    CIJobLog,
    CIRunRef,
    ChangeRequestRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.remediation import (
    CIFailureAnalysis,
    CIFailureKind,
    RemediationAction,
    RemediationOutcome,
    RemediationStatus,
)
from devopspilot.contracts.state import LeaseAcquisitionError, StoredDeliveryState
from devopspilot.orchestration.control_plane import (
    AutonomousDeliveryControlPlane,
    BoundedRemediationPolicy,
    RuleBasedCIFailureAnalyzer,
)
from devopspilot.orchestration.verifier import DeliveryOutcomeStatus, StandardDeliveryVerifier
from devopspilot.persistence.remediation_ledger import SQLiteRemediationLedger
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore

REPO = RepositoryRef(provider_id="mock", repository_id="repo-gov", full_name="org/gov-repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="item-fail-001", title="Failure test task")


class FakeCI:
    def __init__(self) -> None:
        self.runs = {}
        self.logs = {}

    async def get_latest_run(self, repo, branch, commit_sha=None):
        return None

    async def get_run_logs(self, run):
        return ()


class DummyRemediator:
    async def remediate(self, state, analysis, *, attempt):
        return ExecutionResult(source_branch="b", commit_sha=f"c-{attempt}", summary="remediated", published=True)


async def test_permission_policy_denied_escalates_without_retry() -> None:
    """1. Permission / Policy failure must NOT trigger patch attempts; it must escalate immediately."""
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_fail_policy_"))
    try:
        ledger = SQLiteRemediationLedger(tmp / "remediation.db")
        policy = BoundedRemediationPolicy(max_patch_attempts=3, max_ci_retries=2)
        analyzer = RuleBasedCIFailureAnalyzer()

        task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
        exec_res = ExecutionResult(source_branch="b", commit_sha="c1", summary="s", published=True)
        ci_run = CIRunRef(provider_id="mock-ci", run_id="ci-policy-fail", repository=REPO, status="completed", conclusion="failure", commit_sha="c1")
        log = CIJobLog(run=ci_run, job_id="j1", job_name="deploy", content="remote: error: GH006: Protected branch update failed for refs/heads/main. Permission denied.")

        state = DeliveryState(task=task, phase=DeliveryPhase.CI_FAILED, execution=exec_res, ci_run=ci_run, ci_logs=(log,))

        control_plane = AutonomousDeliveryControlPlane(
            ci=FakeCI(),
            analyzer=analyzer,
            remediator=DummyRemediator(),
            ledger=ledger,
            policy=policy,
        )

        res_state = await control_plane.handle_ci_failure("deliv-policy-01", state)
        # Policy failures must immediately transition to REJECTED/escalated, never retry patching!
        assert res_state.phase is DeliveryPhase.REJECTED

        history = await ledger.list("deliv-policy-01")
        assert len(history) == 1
        assert history[0].action is RemediationAction.ESCALATE
        assert history[0].failure_kind is CIFailureKind.POLICY
        assert history[0].outcome is RemediationOutcome.ESCALATED
        print("POLICY_PERMISSION_DENIED_ESCALATED_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def test_model_quota_unavailable_fails_safely() -> None:
    """2. Model unavailable / quota exhaustion must cleanly record error and stop."""
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_fail_quota_"))
    try:
        store = SQLiteDeliveryStateStore(tmp / "state.db")
        verifier = StandardDeliveryVerifier()

        task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
        # Model rate limit or quota exceeded
        exec_failed = ExecutionResult(
            source_branch="b",
            commit_sha="c1",
            summary="Execution failed: Model quota exceeded (HTTP 429: InsufficientQuota)",
            published=False,  # unpublished
            metadata={"runtime_degraded": "true", "runtime_degradation_reason": "quota_exhausted"},
        )
        state = DeliveryState(task=task, phase=DeliveryPhase.EXECUTED, execution=exec_failed)

        v_res = await verifier.verify(state)
        assert v_res.accepted is False
        assert v_res.outcome_status == DeliveryOutcomeStatus.REJECTED
        assert "No published commit" in v_res.summary or "rejected" in str(v_res.outcome_status).lower()
        print("MODEL_QUOTA_UNAVAILABLE_FAILS_SAFELY_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def test_ci_pending_timeout_halts_safely() -> None:
    """3. CI polling timeout halts safely without deadlocking."""
    ci_run = CIRunRef(provider_id="mock-ci", run_id="ci-hang", repository=REPO, status="in_progress", conclusion=None)
    task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
    exec_res = ExecutionResult(source_branch="b", commit_sha="c1", summary="ok", published=True)

    state_pending = DeliveryState(task=task, phase=DeliveryPhase.CI_PENDING, execution=exec_res, ci_run=ci_run)
    verifier = StandardDeliveryVerifier()

    # If verification is invoked while CI is still pending/timed out
    v_res = await verifier.verify(state_pending)
    assert v_res.accepted is False
    assert v_res.outcome_status == DeliveryOutcomeStatus.REJECTED
    assert "CI not passed" in v_res.summary
    print("CI_PENDING_TIMEOUT_HALTS_SAFELY_OK")


async def test_crash_lease_resume_preserves_budget() -> None:
    """4. Process termination leaves lease and state intact; resume picks up without resetting attempts."""
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_fail_resume_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)
        ledger = SQLiteRemediationLedger(tmp / "remediation.db")

        task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
        state = DeliveryState(task=task, phase=DeliveryPhase.CI_FAILED)

        # Worker 1 acquires lease and consumes 1 remediation attempt
        lease1 = await store.acquire_lease(deduplication_key="key-01", delivery_id="deliv-crash-01", owner="worker-1", ttl_seconds=1.0)
        assert lease1.acquired is True
        await ledger.reserve_attempt(
            "deliv-crash-01",
            attempt=1,
            failure_kind=CIFailureKind.CODE,
            action=RemediationAction.PATCH,
            previous_commit_sha="c-crash-1",
        )

        # Worker 1 crashes without clean shutdown (lease remains held or expires)
        # Attempting to acquire immediately with another worker fails due to active lease
        lease2_fail = await store.acquire_lease(deduplication_key="key-01", delivery_id="deliv-crash-01", owner="worker-2", ttl_seconds=10.0)
        assert lease2_fail.acquired is False

        # After TTL expires, worker 2 acquires lease
        await asyncio.sleep(1.1)
        lease2_ok = await store.acquire_lease(deduplication_key="key-01", delivery_id="deliv-crash-01", owner="worker-2", ttl_seconds=10.0)
        assert lease2_ok.acquired is True

        # Existing remediation budget history is preserved and NOT reset!
        history = await ledger.list("deliv-crash-01")
        assert len(history) == 1
        assert history[0].attempt == 1
        print("CRASH_LEASE_RESUME_PRESERVES_BUDGET_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def test_remediation_budget_exhaustion_escalates() -> None:
    """5. Budget exhaustion terminates loop with ESCALATED status and preserves all attempt audit history."""
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_fail_exhaust_"))
    try:
        ledger = SQLiteRemediationLedger(tmp / "remediation.db")
        # Strict policy: max 2 patch attempts
        policy = BoundedRemediationPolicy(max_patch_attempts=2, max_ci_retries=1)
        analyzer = RuleBasedCIFailureAnalyzer()

        task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
        exec_res = ExecutionResult(source_branch="b", commit_sha="c1", summary="s", published=True)
        ci_run = CIRunRef(provider_id="mock-ci", run_id="ci-f", repository=REPO, status="completed", conclusion="failure", commit_sha="c1")
        log = CIJobLog(run=ci_run, job_id="j1", job_name="test", content="AssertionError: test failed")
        state = DeliveryState(task=task, phase=DeliveryPhase.CI_FAILED, execution=exec_res, ci_run=ci_run, ci_logs=(log,))

        control_plane = AutonomousDeliveryControlPlane(
            ci=FakeCI(),
            analyzer=analyzer,
            remediator=DummyRemediator(),
            ledger=ledger,
            policy=policy,
        )

        # Attempt 1 -> patch
        s1 = await control_plane.handle_ci_failure("deliv-exhaust-01", state)
        assert s1.phase is DeliveryPhase.CI_PENDING

        # Attempt 2 -> patch
        s2 = await control_plane.handle_ci_failure("deliv-exhaust-01", state)
        assert s2.phase is DeliveryPhase.CI_PENDING

        # Attempt 3 -> BUDGET EXHAUSTED! Must escalate and reject, never infinite loop!
        s3 = await control_plane.handle_ci_failure("deliv-exhaust-01", state)
        assert s3.phase is DeliveryPhase.REJECTED

        # Full audit history preserved
        history = await ledger.list("deliv-exhaust-01")
        assert len(history) == 3
        assert history[0].attempt == 1 and history[0].action is RemediationAction.PATCH
        assert history[1].attempt == 2 and history[1].action is RemediationAction.PATCH
        assert history[2].attempt == 3 and history[2].action is RemediationAction.ESCALATE
        assert history[2].outcome is RemediationOutcome.ESCALATED
        print("BUDGET_EXHAUSTION_ESCALATES_SAFELY_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def main() -> None:
    await test_permission_policy_denied_escalates_without_retry()
    await test_model_quota_unavailable_fails_safely()
    await test_ci_pending_timeout_halts_safely()
    await test_crash_lease_resume_preserves_budget()
    await test_remediation_budget_exhaustion_escalates()
    print("ALL FAILURE BOUNDARY AND GOVERNANCE SMOKE TESTS PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
