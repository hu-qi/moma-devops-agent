"""Smoke test for StandardDeliveryVerifier and multi-dimensional outcome evaluation."""

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
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.review import ReviewResult, ReviewVerdict
from devopspilot.orchestration.verifier import (
    DeliveryOutcomeStatus,
    StandardDeliveryVerifier,
)

REPO = RepositoryRef(provider_id="mock", repository_id="repo-1", full_name="org/repo")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="1", title="test item")
TASK = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
CHANGE = ChangeRequestRef(repository=REPO, change_id="101", title="pr", source_branch="b", target_branch="main", state="open")


def make_state(
    *,
    phase: DeliveryPhase = DeliveryPhase.CI_PASSED,
    ci_conclusion: str = "success",
    has_commit: bool = True,
    review_verdict: ReviewVerdict = ReviewVerdict.APPROVED,
    trajectory_id: str = "traj-1",
    event_count: int = 5,
    capture_issues: int = 0,
    runtime_degraded: bool = False,
    degradation_reason: str = "",
) -> DeliveryState:
    ci_run = CIRunRef(
        provider_id="mock",
        run_id="ci-1",
        repository=REPO,
        status="completed",
        conclusion=ci_conclusion,
        commit_sha="c12345" if has_commit else "",
    )
    review = ReviewResult(
        reviewer_id="reviewer-1",
        verdict=review_verdict,
        diff_digest="digest-123",
        summary="ok",
    )
    execution = ExecutionResult(
        source_branch="b",
        commit_sha="c12345" if has_commit else "",
        summary="done",
        published=True,
        review=review,
        metadata={
            "trajectory_id": trajectory_id,
            "trajectory_event_count": str(event_count),
            "capture_issues": str(capture_issues),
            "runtime_degraded": "true" if runtime_degraded else "false",
            "runtime_degradation_reason": degradation_reason,
        },
    )
    return DeliveryState(
        task=TASK,
        phase=phase,
        execution=execution,
        change_request=CHANGE,
        ci_run=ci_run,
    )


def test_verifier_scenarios() -> None:
    verifier = StandardDeliveryVerifier()

    # 1. Negative: CI failed -> REJECTED
    s1 = make_state(phase=DeliveryPhase.CI_FAILED, ci_conclusion="failure")
    r1 = asyncio.run(verifier.verify(s1))
    assert r1.accepted is False
    assert r1.outcome_status == DeliveryOutcomeStatus.REJECTED
    print("VERIFIER_CI_FAILED_REJECTED_OK")

    # 2. Negative: Review rejected -> REJECTED
    s2 = make_state(review_verdict=ReviewVerdict.REJECTED)
    r2 = asyncio.run(verifier.verify(s2))
    assert r2.accepted is False
    assert r2.outcome_status == DeliveryOutcomeStatus.REJECTED
    print("VERIFIER_REVIEW_REJECTED_OK")

    # 3. Negative: Empty trajectory -> EVIDENCE_INCOMPLETE (cannot claim complete delivery!)
    s3 = make_state(event_count=0)
    r3 = asyncio.run(verifier.verify(s3))
    assert r3.accepted is False
    assert r3.outcome_status == DeliveryOutcomeStatus.EVIDENCE_INCOMPLETE
    assert r3.evidence_completeness is False
    assert r3.escalation_path != ""
    print("VERIFIER_EMPTY_TRAJECTORY_BLOCKED_OK")

    # 4. Negative: Capture issues -> EVIDENCE_INCOMPLETE
    s4 = make_state(capture_issues=2)
    r4 = asyncio.run(verifier.verify(s4))
    assert r4.accepted is False
    assert r4.outcome_status == DeliveryOutcomeStatus.EVIDENCE_INCOMPLETE
    assert r4.evidence_completeness is False
    print("VERIFIER_CAPTURE_ISSUES_BLOCKED_OK")

    # 5. Degraded: Runtime timeout -> VERIFIED_DEGRADED (accepted with explicit reason & path)
    s5 = make_state(runtime_degraded=True, degradation_reason="agentteam_timeout")
    r5 = asyncio.run(verifier.verify(s5))
    assert r5.accepted is True
    assert r5.outcome_status == DeliveryOutcomeStatus.VERIFIED_DEGRADED
    assert r5.runtime_clean_completion is False
    assert r5.degradation_reason == "agentteam_timeout"
    assert "human_review" in r5.escalation_path
    print("VERIFIER_RUNTIME_DEGRADED_ACCEPTED_WITH_AUDIT_OK")

    # 6. Positive: Clean verified delivery
    s6 = make_state()
    r6 = asyncio.run(verifier.verify(s6))
    assert r6.accepted is True
    assert r6.outcome_status == DeliveryOutcomeStatus.VERIFIED_CLEAN
    assert r6.task_success is True
    assert r6.runtime_clean_completion is True
    assert r6.evidence_completeness is True
    print("VERIFIER_ALL_CLEAN_OK")


def main() -> None:
    test_verifier_scenarios()
    print("ALL DELIVERY VERIFIER SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
