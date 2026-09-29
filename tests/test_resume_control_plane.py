"""C11: resume() drives the durable remediation control plane on CI failure."""

import asyncio
import sys
from dataclasses import replace
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from devopspilot.contracts.delivery import (
    DeliveryPhase, DeliveryState, DeliveryTask, ExecutionResult,
)
from devopspilot.contracts.providers import CIRunRef, RepositoryRef, WorkItemRef
from devopspilot.contracts.remediation import (
    CIFailureAnalysis, CIFailureKind, RemediationAction, RemediationOutcome,
    RemediationRecord, RemediationStatus,
)
from devopspilot.orchestration.control_plane import BoundedRemediationPolicy, RuleBasedCIFailureAnalyzer
from devopspilot.persistence.remediation_ledger import SQLiteRemediationLedger
from devopspilot.orchestration.service import DeliveryOrchestrator


class FakeSCM:
    async def get_repository(self, rid):
        return RepositoryRef(provider_id="mock", repository_id="r1", full_name=rid, default_branch="main")

    async def get_work_item(self, repo, iid):
        return WorkItemRef(repository=repo, item_id=iid, title="t")


class FakeCI:
    async def capabilities(self):
        return frozenset()

    async def list_runs(self, *a, **kw):
        return ()

    async def retry_failed(self, run):
        return replace(run, status="in_progress")


class RepairExecutor:
    """Pretends to be the base executor and supports remediate()."""

    async def execute(self, task):
        raise AssertionError("not used in this test")

    async def remediate(self, state, analysis, *, attempt):
        # Same-branch, new-commit repair (control plane enforces both)
        assert state.execution.source_branch == "b"
        return replace(state.execution, commit_sha=f"fix-{attempt}")


class EscalatingAnalyzer(RuleBasedCIFailureAnalyzer):
    async def analyze(self, state):
        return CIFailureAnalysis(kind=CIFailureKind.CODE, summary="test failure", evidence=("e1",))


def _failed_state() -> DeliveryState:
    repo = RepositoryRef(provider_id="mock", repository_id="r1", full_name="org/repo")
    item = WorkItemRef(repository=repo, item_id="42", title="t")
    exec_res = ExecutionResult(source_branch="b", commit_sha="c1", summary="s", published=True)
    ci = CIRunRef(provider_id="mock", run_id="r1", repository=repo, status="completed",
                  conclusion="failure", commit_sha="c1")
    return DeliveryState(
        task=DeliveryTask(repository=repo, work_item=item, target_branch="main"),
        phase=DeliveryPhase.CI_FAILED, execution=exec_res, ci_run=ci,
    )


def test_resume_on_ci_failure_goes_through_control_plane(tmp_path: Path) -> None:
    import devopspilot.persistence.sqlite_state as ss_mod
    from devopspilot.orchestration.control_plane import AutonomousDeliveryControlPlane

    db = tmp_path / "state.db"
    store = ss_mod.SQLiteDeliveryStateStore(db)
    state = _failed_state()
    asyncio.run(store.save("d1", state, expected_version=0))

    ledger = SQLiteRemediationLedger(tmp_path / "remediation.db")
    control_plane = AutonomousDeliveryControlPlane(
        ci=FakeCI(),
        analyzer=EscalatingAnalyzer(),
        remediator=RepairExecutor(),
        ledger=ledger,
        policy=BoundedRemediationPolicy(max_patch_attempts=2, max_ci_retries=0),
    )
    # loop is unused for the CI_FAILED branch when control_plane handles it
    orch = DeliveryOrchestrator(loop=None, store=store, control_plane=control_plane)  # type: ignore[arg-type]
    saved = asyncio.run(orch.resume("d1"))

    # Repair produced a new commit on the same branch and queued CI again
    assert saved.state.phase is DeliveryPhase.CI_PENDING
    assert saved.state.execution.commit_sha == "fix-1"

    # Budget was reserved in the durable ledger BEFORE the external action
    records = asyncio.run(ledger.list("d1"))
    assert len(records) == 1
    assert records[0].status is RemediationStatus.COMPLETED
    assert records[0].outcome is RemediationOutcome.COMPLETED
    assert records[0].resulting_commit_sha == "fix-1"
    print("RESUME_CI_FAILURE_CONTROL_PLANE_OK")


def test_retry_after_crash_does_not_reset_budget(tmp_path: Path) -> None:
    import devopspilot.persistence.sqlite_state as ss_mod
    from devopspilot.orchestration.control_plane import AutonomousDeliveryControlPlane

    db = tmp_path / "state.db"
    store = ss_mod.SQLiteDeliveryStateStore(db)
    asyncio.run(store.save("d2", _failed_state(), expected_version=0))

    ledger = SQLiteRemediationLedger(tmp_path / "remediation.db")
    # Simulate a crash after a previous reserved attempt: pre-seed ledger
    asyncio.run(ledger.reserve_attempt(
        delivery_id="d2", attempt=1, failure_kind=CIFailureKind.CODE,
        action=RemediationAction.PATCH, previous_commit_sha="c1",
    ))
    control_plane = AutonomousDeliveryControlPlane(
        ci=FakeCI(),
        analyzer=EscalatingAnalyzer(),
        remediator=RepairExecutor(),
        ledger=ledger,
        policy=BoundedRemediationPolicy(max_patch_attempts=2, max_ci_retries=0),
    )
    orch = DeliveryOrchestrator(loop=None, store=store, control_plane=control_plane)  # type: ignore[arg-type]
    saved = asyncio.run(orch.resume("d2"))

    # Attempt counter continued from history (2), not reset to 1
    assert saved.state.execution.commit_sha == "fix-2"
    records = asyncio.run(ledger.list("d2"))
    assert [r.attempt for r in records] == [1, 2]
    print("BUDGET_NOT_RESET_AFTER_CRASH_OK")


def main() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        test_resume_on_ci_failure_goes_through_control_plane(base / "a")
        test_retry_after_crash_does_not_reset_budget(base / "b")
    print("ALL C11 RESUME CONTROL PLANE TESTS PASSED.")


if __name__ == "__main__":
    main()
