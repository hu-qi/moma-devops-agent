"""Credential-free smoke for bounded, restart-safe CI remediation."""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import replace
from pathlib import Path

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import (
    CIArtifactRef,
    CICapability,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.remediation import (
    CIFailureAnalysis,
    CIFailureKind,
    RemediationAction,
)
from devopspilot.orchestration.control_plane import (
    AutonomousDeliveryControlPlane,
    BoundedRemediationPolicy,
    RuleBasedCIFailureAnalyzer,
)
from devopspilot.orchestration.control_plane_service import (
    AutonomousDeliveryOrchestrator,
)
from devopspilot.persistence import (
    SQLiteDeliveryStateStore,
    SQLiteRemediationLedger,
)


class FakeCI:
    provider_id = "fake-ci"

    def __init__(self) -> None:
        self.retry_calls = 0

    async def capabilities(self):
        return frozenset({CICapability.RUNS, CICapability.LOGS, CICapability.RETRY})

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        self.retry_calls += 1
        return replace(run, status="queued", conclusion=None)

    async def get_run(self, repository, run_id):
        raise NotImplementedError

    async def list_runs(
        self, repository, *, commit_sha=None, ref=None, status=None, limit=20,
    ):
        raise NotImplementedError

    async def stream_logs(self, run):
        if False:
            yield None

    async def trigger(self, repository, *, ref, workflow_id=None, inputs=None):
        raise NotImplementedError

    async def cancel(self, run):
        return None

    async def list_artifacts(self, run) -> tuple[CIArtifactRef, ...]:
        return ()


class FakeRemediator:
    def __init__(self) -> None:
        self.calls = 0

    async def remediate(
        self,
        state: DeliveryState,
        analysis: CIFailureAnalysis,
        *,
        attempt: int,
    ) -> ExecutionResult:
        self.calls += 1
        assert analysis.kind is CIFailureKind.CODE
        assert state.execution is not None
        return replace(
            state.execution,
            commit_sha=f"repair-{attempt}",
            summary=f"repair attempt {attempt}",
            published=True,
        )


def failed_state(*, commit_sha: str = "broken-0", run_id: str = "100") -> DeliveryState:
    repository = RepositoryRef(
        provider_id="github",
        repository_id="1",
        full_name="acme/demo",
        default_branch="main",
    )
    task = DeliveryTask(
        repository=repository,
        work_item=WorkItemRef(
            repository=repository,
            item_id="7",
            title="Repair deterministic fixture",
        ),
        target_branch="main",
    )
    run = CIRunRef(
        provider_id="github-actions",
        run_id=run_id,
        repository=repository,
        status="completed",
        conclusion="failure",
        commit_sha=commit_sha,
    )
    return DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=ExecutionResult(
            source_branch="devopspilot/fix-7",
            commit_sha=commit_sha,
            summary="candidate",
            published=True,
        ),
        ci_run=run,
        ci_logs=(
            CIJobLog(
                run=run,
                job_id="test",
                job_name="fixture-test",
                content='AssertionError: assert status() == "fixed"',
            ),
        ),
    )


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="devopspilot_control_plane_") as tmp:
        db = Path(tmp) / "control-plane.sqlite3"
        store = SQLiteDeliveryStateStore(db)
        ledger = SQLiteRemediationLedger(db)
        ci = FakeCI()
        remediator = FakeRemediator()
        control_plane = AutonomousDeliveryControlPlane(
            ci=ci,
            analyzer=RuleBasedCIFailureAnalyzer(),
            remediator=remediator,
            ledger=ledger,
            policy=BoundedRemediationPolicy(max_patch_attempts=1, max_ci_retries=1),
        )
        service = AutonomousDeliveryOrchestrator(
            control_plane=control_plane,
            store=store,
        )

        initial = failed_state()
        seeded = await store.save("delivery-7", initial, expected_version=0)
        assert seeded.version == 1

        repaired = await service.remediate_ci_failure("delivery-7")
        assert repaired.version == 2
        assert repaired.state.phase is DeliveryPhase.CI_PENDING
        assert repaired.state.execution is not None
        assert repaired.state.execution.commit_sha == "repair-1"
        assert remediator.calls == 1

        history = await ledger.list("delivery-7")
        assert len(history) == 1
        assert history[0].action is RemediationAction.PATCH
        assert history[0].resulting_commit_sha == "repair-1"

        run2 = replace(
            initial.ci_run,
            run_id="101",
            commit_sha="repair-1",
        )
        failed_again = replace(
            repaired.state,
            phase=DeliveryPhase.CI_FAILED,
            ci_run=run2,
            ci_logs=(
                CIJobLog(
                    run=run2,
                    job_id="test-2",
                    job_name="fixture-test",
                    content="AssertionError: regression remains",
                ),
            ),
        )
        saved_again = await store.save(
            "delivery-7",
            failed_again,
            expected_version=repaired.version,
        )
        assert saved_again.version == 3

        restarted_service = AutonomousDeliveryOrchestrator(
            control_plane=AutonomousDeliveryControlPlane(
                ci=FakeCI(),
                analyzer=RuleBasedCIFailureAnalyzer(),
                remediator=FakeRemediator(),
                ledger=SQLiteRemediationLedger(db),
                policy=BoundedRemediationPolicy(
                    max_patch_attempts=1,
                    max_ci_retries=1,
                ),
            ),
            store=SQLiteDeliveryStateStore(db),
        )
        escalated = await restarted_service.remediate_ci_failure("delivery-7")
        assert escalated.version == 4
        assert escalated.state.phase is DeliveryPhase.REJECTED
        assert escalated.state.verification is not None
        assert "Human escalation required" in escalated.state.verification.summary

        durable_history = await SQLiteRemediationLedger(db).list("delivery-7")
        assert len(durable_history) == 2
        assert durable_history[-1].action is RemediationAction.ESCALATE

        infra = failed_state(commit_sha="infra-0", run_id="200")
        assert infra.ci_run is not None
        infra = replace(
            infra,
            ci_logs=(
                CIJobLog(
                    run=infra.ci_run,
                    job_id="runner",
                    job_name="runner",
                    content="runner lost communication: connection reset",
                ),
            ),
        )
        infra_db = Path(tmp) / "infra.sqlite3"
        infra_ci = FakeCI()
        infra_plane = AutonomousDeliveryControlPlane(
            ci=infra_ci,
            analyzer=RuleBasedCIFailureAnalyzer(),
            remediator=FakeRemediator(),
            ledger=SQLiteRemediationLedger(infra_db),
        )
        retried = await infra_plane.handle_ci_failure("infra-delivery", infra)
        assert retried.phase is DeliveryPhase.CI_PENDING
        assert infra_ci.retry_calls == 1

    print("AUTONOMOUS_CONTROL_PLANE_PATCH_OK")
    print("AUTONOMOUS_CONTROL_PLANE_DURABLE_BUDGET_OK")
    print("AUTONOMOUS_CONTROL_PLANE_ESCALATION_OK")
    print("AUTONOMOUS_CONTROL_PLANE_INFRA_RETRY_OK")


if __name__ == "__main__":
    asyncio.run(main())
