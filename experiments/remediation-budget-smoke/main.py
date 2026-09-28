"""Smoke test for remediation attempt pre-reservation, budget protection, and crash-safe ledger audit."""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from dataclasses import replace
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
    CICapability,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.remediation import (
    CIFailureAnalysis,
    CIFailureAnalyzer,
    CIFailureKind,
    RemediationAction,
    RemediationExecutor,
    RemediationOutcome,
    RemediationStatus,
)
from devopspilot.orchestration.control_plane import (
    AutonomousDeliveryControlPlane,
    BoundedRemediationPolicy,
)
from devopspilot.persistence.remediation_ledger import SQLiteRemediationLedger

REPO = RepositoryRef(provider_id="mock", repository_id="repo-1", full_name="org/repo")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="item-1", title="test")
TASK = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")


class StaticAnalyzer(CIFailureAnalyzer):
    async def analyze(self, state: DeliveryState) -> CIFailureAnalysis:
        return CIFailureAnalysis(CIFailureKind.CODE, "code error detected")


class CrashingRemediator(RemediationExecutor):
    def __init__(self, crash_on_attempts: set[int]) -> None:
        self.crash_on_attempts = crash_on_attempts
        self.call_count = 0

    async def remediate(
        self,
        state: DeliveryState,
        analysis: CIFailureAnalysis,
        *,
        attempt: int,
    ) -> ExecutionResult:
        self.call_count += 1
        if attempt in self.crash_on_attempts:
            raise RuntimeError(f"Simulated crash on attempt {attempt}")
        return ExecutionResult(
            source_branch=state.execution.source_branch if state.execution else "branch",
            commit_sha=f"repaired-{attempt}",
            summary="repaired",
            published=True,
        )


class MockCI:
    async def capabilities(self) -> frozenset[CICapability]:
        return frozenset()

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        return run


def make_failed_state() -> DeliveryState:
    run = CIRunRef(provider_id="mock", run_id="run-1", repository=REPO, status="completed", conclusion="failure")
    exec_res = ExecutionResult(source_branch="b", commit_sha="c001", summary="s", published=True)
    return DeliveryState(
        task=TASK,
        phase=DeliveryPhase.CI_FAILED,
        execution=exec_res,
        ci_run=run,
        ci_logs=(CIJobLog(run=run, job_id="j1", job_name="test", content="assertion error"),),
    )


async def test_crash_preserves_budget_and_prevents_unbounded_retries() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_remed_budget_"))
    try:
        db_path = tmp / "ledger.db"
        ledger = SQLiteRemediationLedger(db_path)
        # Max 2 patch attempts
        policy = BoundedRemediationPolicy(max_patch_attempts=2, max_ci_retries=0)
        remediator = CrashingRemediator(crash_on_attempts={1})  # Crash on attempt 1
        cp = AutonomousDeliveryControlPlane(
            ci=MockCI(),  # type: ignore[arg-type]
            analyzer=StaticAnalyzer(),
            remediator=remediator,
            ledger=ledger,
            policy=policy,
        )

        state = make_failed_state()

        # 1. First execution crashes during remediate
        try:
            await cp.handle_ci_failure("deliv-1", state)
            assert False, "Should have crashed"
        except RuntimeError as exc:
            assert "Simulated crash on attempt 1" in str(exc)

        # Verify ledger has reserved and marked attempt 1 as FAILED (budget consumed!)
        history1 = await ledger.list("deliv-1")
        assert len(history1) == 1
        assert history1[0].attempt == 1
        assert history1[0].status == RemediationStatus.FAILED
        assert "Simulated crash" in history1[0].error_message
        print("ATTEMPT_1_CRASH_AUDITED_OK")

        # 2. Second execution (attempt 2) succeeds
        next_state = await cp.handle_ci_failure("deliv-1", state)
        assert next_state.phase is DeliveryPhase.CI_PENDING
        assert next_state.execution is not None
        assert next_state.execution.commit_sha == "repaired-2"

        history2 = await ledger.list("deliv-1")
        assert len(history2) == 2
        assert history2[1].attempt == 2
        assert history2[1].status == RemediationStatus.COMPLETED
        print("ATTEMPT_2_SUCCEEDED_OK")

        # 3. Third execution exceeds max_patch_attempts (2) -> must ESCALATE, never retry blindly
        third_state = await cp.handle_ci_failure("deliv-1", state)
        assert third_state.phase is DeliveryPhase.REJECTED
        assert third_state.verification is not None
        assert third_state.verification.accepted is False
        assert "Human escalation required" in third_state.verification.summary

        history3 = await ledger.list("deliv-1")
        assert len(history3) == 3
        assert history3[2].attempt == 3
        assert history3[2].outcome == RemediationOutcome.ESCALATED
        print("BUDGET_EXCEEDED_ESCALATED_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def main() -> None:
    await test_crash_preserves_budget_and_prevents_unbounded_retries()
    print("ALL REMEDIATION BUDGET SMOKE TESTS PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
