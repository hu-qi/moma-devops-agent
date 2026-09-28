"""Smoke test for governed self-evolution: report/trajectory mining, offline gate, negative gain rejection, synthetic approval block, and rollback."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionRequest,
    HumanPromotionApproval,
    UnauthorizedPromotionError,
)
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.evolution.engine import EvolutionEngine
from devopspilot.evolution.gate import RegressionGate
from devopspilot.evolution.miner import DeliveryEvolutionMiner

REPO = RepositoryRef(provider_id="mock", repository_id="repo-evo", full_name="org/evo-repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="item-evo-101", title="task for evolution")


def test_trajectory_mining_with_task_id_thread() -> None:
    miner = DeliveryEvolutionMiner()
    task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
    exec_res = ExecutionResult(
        source_branch="feat",
        commit_sha="c1",
        summary="done",
        published=True,
        metadata={
            "trajectory_id": "traj-xyz-999",
            "runtime_degraded": "true",
            "runtime_degradation_reason": "deadlock_detected",
        },
    )
    state = DeliveryState(task=task, phase=DeliveryPhase.VERIFIED, execution=exec_res)

    opps = miner.mine(state)
    assert len(opps) == 1
    opp = opps[0]
    # Task ID and Trajectory ID thread through the opportunity
    assert "item-evo-101" in opp.opportunity_id
    assert opp.source_trajectory_ids == ("traj-xyz-999",)
    assert opp.target_kind == ArtifactKind.TEAM_PATTERN
    print("EVOLUTION_TRAJECTORY_MINING_OK")


def test_gate_negative_gain_rejection_and_pending_human() -> None:
    gate = RegressionGate()
    base_art = ArtifactVersion(artifact_id="skill-1", kind=ArtifactKind.SKILL, version="1.0.0", content="def old(): pass")
    cand_art = ArtifactVersion(artifact_id="skill-1", kind=ArtifactKind.SKILL, version="1.1.0", content="def new(): pass")
    candidate = EvolutionCandidate(
        candidate_id="cand-001",
        artifact=cand_art,
        base_artifact_id="skill-1",
        base_version="1.0.0",
        provider_id="test-provider",
        change_summary="Optimized skill",
        source_trajectory_ids=("traj-xyz-999",),
    )
    request = EvolutionRequest(
        request_id="req-1",
        base_artifact=base_art,
        objective="Improve skill",
        source_trajectory_ids=("traj-xyz-999",),
        evaluation_cases=("case-1", "case-2"),
    )

    class DummyProvider:
        @property
        def provider_id(self) -> str:
            return "dummy"

        async def generate_candidate(self, req: EvolutionRequest) -> EvolutionCandidate:
            return candidate

    engine = EvolutionEngine(provider=DummyProvider(), gate=gate)

    # 1. Negative Gain / Regression: Candidate causes task_success regression
    baseline = (
        BenchmarkObservation(case_id="case-1", task_success=True, tool_calls=5, duration_ms=1000),
        BenchmarkObservation(case_id="case-2", task_success=True, tool_calls=5, duration_ms=1000),
    )
    regressed_results = (
        BenchmarkObservation(case_id="case-1", task_success=False, tool_calls=5, duration_ms=1000),  # regressed!
        BenchmarkObservation(case_id="case-2", task_success=True, tool_calls=5, duration_ms=1000),
    )
    ev_neg = engine.evaluate(request=request, candidate=candidate, baseline=baseline, candidate_results=regressed_results)
    assert ev_neg.gate_passed is False
    assert len(ev_neg.regressions) > 0

    dec_neg = engine.await_human_approval(candidate=candidate, evidence=ev_neg)
    assert dec_neg.state == ApprovalState.REJECTED
    assert "Candidate failed the automated gate" in dec_neg.reason
    print("NEGATIVE_GAIN_REJECTED_OK")

    # 2. Positive Gain: Candidate improves duration and tool calls with no regressions
    improved_results = (
        BenchmarkObservation(case_id="case-1", task_success=True, tool_calls=3, duration_ms=700),
        BenchmarkObservation(case_id="case-2", task_success=True, tool_calls=3, duration_ms=700),
    )
    ev_pos = engine.evaluate(request=request, candidate=candidate, baseline=baseline, candidate_results=improved_results)
    assert ev_pos.gate_passed is True
    assert "tool_calls" in ev_pos.improved_metrics

    # Must be held at PENDING_HUMAN, never auto-promoted!
    dec_pos = engine.await_human_approval(candidate=candidate, evidence=ev_pos)
    assert dec_pos.state == ApprovalState.PENDING_HUMAN
    assert dec_pos.rollback_version == "1.0.0"
    print("POSITIVE_GAIN_HELD_AT_PENDING_HUMAN_OK")

    # 3. Unauthorized Promotion: Synthetic approval attempting to promote to production is BLOCKED
    synthetic_approval = HumanPromotionApproval(
        approver="mock_test_bot",
        sign_off=True,
        production=True,
        synthetic=True,
        notes="Automated synthetic approval",
    )
    try:
        engine.promote_to_production(decision=dec_pos, approval=synthetic_approval)
        assert False, "Should have blocked synthetic approval from promoting to production"
    except UnauthorizedPromotionError as exc:
        assert "Synthetic or mock approvals are strictly prohibited" in str(exc)
        print("SYNTHETIC_APPROVAL_PRODUCTION_PROMOTION_BLOCKED_OK")

    # 4. Legitimate Human Approval: Verified human sign-off succeeds
    human_approval = HumanPromotionApproval(
        approver="alice_chief_engineer",
        sign_off=True,
        production=True,
        synthetic=False,
        notes="Verified benchmark improvements on staging",
    )
    promoted = engine.promote_to_production(decision=dec_pos, approval=human_approval)
    assert promoted.state == ApprovalState.APPROVED
    assert promoted.rollback_version == "1.0.0"
    assert "Promoted to production by alice_chief_engineer" in promoted.reason
    print("LEGITIMATE_HUMAN_PROMOTION_OK")

    # 5. Rollback mechanism
    rollback_decision = engine.rollback(
        artifact_id="skill-1",
        target_version=promoted.rollback_version,
        decided_by="alice_chief_engineer",
        reason="Staging canary anomaly detected",
    )
    assert rollback_decision.state == ApprovalState.APPROVED
    assert rollback_decision.target_version == "1.0.0"
    print("ROLLBACK_MECHANISM_OK")


def main() -> None:
    test_trajectory_mining_with_task_id_thread()
    test_gate_negative_gain_rejection_and_pending_human()
    print("ALL GOVERNED EVOLUTION SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
