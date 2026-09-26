"""Credential-free smoke for bounded, durable CI remediation."""

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
    CIJobLog,
    CIRunRef,
    CICapability,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.remediation import (
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
from devopspilot.persistence.remediation_ledger import SQLiteRemediationLedger
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore


class FakeCI:
    provider_id = "fake-ci"

    def __init__(self) -> None:
        self.retry_calls = 0

    async def capabilities(self):
        return frozenset({CICapability.RUNS, CICapability.LOGS, CICapability.RETRY})

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        self.retry_calls += 1
        return replace(run, status="queued", conclusion=None)


class FakeRemediator:
    def __init__(self) -> None:
        self.calls = 0

    async def remediate(self, state, analysis, *, attempt):
        assert state.execution is not None
        assert analysis.kind is CIFailureKind.CODE
        self.calls += 1
        return ExecutionResult(
            source_branch=state.execution.source_branch,
            commit_sha=f"repair-{attempt}",
            summary=f"repair attempt {attempt}",
            published=True,
            test_summary="local verification passed",
        )


def failed_state(message: str, *, commit_sha: str = "base-commit") -> DeliveryState:
    repository = RepositoryRef(
        provider_id="fake",
        repository_id="repo-1",
        full_name="acme/demo",
        default_branch="main",
    )
    work_item = WorkItemRef(
        repository=repository,
        item_id="7",
        title="Repair CI",
    )
    task = DeliveryTask(repository, work_item, "main")
    execution = ExecutionResult(
        source_branch="devopspilot/fix-7",
        commit_sha=commit_sha,
        summary="candidate",
        published=True,
    )
    run = CIRunRef(
        provider_id="fake-ci",
        run_id="100",
        repository=repository,
        status="completed",
        conclusion="failure",
        commit_sha=commit_sha,
    )
    log = CIJobLog(run=run, job_id="job-1", job_name="tests", content=message)
    return DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=execution,
        ci_run=run,
        ci_logs=(log,),
    )


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "control-plane.sqlite3"
        ledger = SQLiteRemediationLedger(db)
        store = SQLiteDeliveryStateStore(db)
        ci = FakeCI()
        remediator = FakeRemediator()
        plane = AutonomousDeliveryControlPlane(
            ci=ci,
            analyzer=RuleBasedCIFailureAnalyzer(),
            remediator=remediator,
            ledger=ledger,
            policy=BoundedRemediationPolicy(max_patch_attempts=2, max_ci_retries=1),
        )

        first = failed_state("AssertionError: expected fixed")
        await store.save("delivery-code", first, expected_version=0)
        service = AutonomousDeliveryOrchestrator(control_plane=plane, store=store)
        patched = await service.remediate_ci_failure("delivery-code")
        assert patched.state.phase is DeliveryPhase.CI_PENDING
        assert patched.state.execution.commit_sha == "repair-1"
        history = await ledger.list("delivery-code")
        assert history[0].action is RemediationAction.PATCH

        second_failure = replace(
            patched.state,
            phase=DeliveryPhase.CI_FAILED,
            ci_run=replace(first.ci_run, commit_sha="repair-1"),
            ci_logs=(replace(first.ci_logs[0], content="tests failed again"),),
        )
        persisted_second = await store.save(
            "delivery-code",
            second_failure,
            expected_version=patched.version,
        )
        restarted = AutonomousDeliveryControlPlane(
            ci=ci,
            analyzer=RuleBasedCIFailureAnalyzer(),
            remediator=remediator,
            ledger=SQLiteRemediationLedger(db),
            policy=BoundedRemediationPolicy(max_patch_attempts=2, max_ci_retries=1),
        )
        restarted_store = SQLiteDeliveryStateStore(db)
        restarted_service = AutonomousDeliveryOrchestrator(
            control_plane=restarted,
            store=restarted_store,
        )
        patched_twice = await restarted_service.remediate_ci_failure("delivery-code")
        assert patched_twice.state.execution.commit_sha == "repair-2"

        third_failure = replace(
            patched_twice.state,
            phase=DeliveryPhase.CI_FAILED,
            ci_run=replace(first.ci_run, commit_sha="repair-2"),
            ci_logs=(replace(first.ci_logs[0], content="AssertionError: still broken"),),
        )
        await restarted_store.save(
            "delivery-code",
            third_failure,
            expected_version=patched_twice.version,
        )
        escalated = await restarted_service.remediate_ci_failure("delivery-code")
        assert escalated.state.phase is DeliveryPhase.REJECTED
        assert "Human escalation required" in escalated.state.verification.summary
        history = await ledger.list("delivery-code")
        assert len(history) == 3
        assert history[-1].action is RemediationAction.ESCALATE

        infra = failed_state("runner timed out while downloading dependencies")
        await restarted_store.save("delivery-infra", infra, expected_version=0)
        infra_result = await restarted_service.remediate_ci_failure("delivery-infra")
        assert infra_result.state.phase is DeliveryPhase.CI_PENDING
        assert ci.retry_calls == 1
        infra_history = await ledger.list("delivery-infra")
        assert infra_history[0].action is RemediationAction.RETRY_CI

        policy = failed_state(
            "permission denied: protected branch requires approval"
        )
        await restarted_store.save("delivery-policy", policy, expected_version=0)
        policy_result = await restarted_service.remediate_ci_failure("delivery-policy")
        assert policy_result.state.phase is DeliveryPhase.REJECTED
        policy_history = await ledger.list("delivery-policy")
        assert policy_history[0].action is RemediationAction.ESCALATE

        assert persisted_second.version == 3

    print("CONTROL_PLANE_CODE_REMEDIATION_OK")
    print("CONTROL_PLANE_RESTART_BUDGET_OK")
    print("CONTROL_PLANE_BOUNDED_ESCALATION_OK")
    print("CONTROL_PLANE_INFRA_RETRY_OK")
    print("CONTROL_PLANE_POLICY_ESCALATION_OK")


if __name__ == "__main__":
    asyncio.run(main())
