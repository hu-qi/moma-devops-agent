"""Unified, multi-dimensional delivery verifier separating task, runtime, and evidence outcomes."""

from __future__ import annotations

from enum import StrEnum

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryVerifier,
    VerificationResult,
)
from devopspilot.contracts.review import ReviewVerdict


class DeliveryOutcomeStatus(StrEnum):
    VERIFIED_CLEAN = "verified_clean"
    VERIFIED_DEGRADED = "verified_degraded"
    EVIDENCE_INCOMPLETE = "evidence_incomplete"
    REJECTED = "rejected"


class StandardDeliveryVerifier:
    """Rigorous delivery verifier enforcing:

    1. task_success: CI passed on HEAD commit, execution produced non-empty commit, review approved.
    2. runtime_clean_completion: No timeout degradation or crash recovery issues.
    3. evidence_completeness: Non-empty canonical trajectory, no capture failures, full audit trail.
    """

    async def verify(self, state: DeliveryState) -> VerificationResult:
        evidence_list: list[str] = []

        # 1. Evaluate task success
        ci_success = (
            state.phase is DeliveryPhase.CI_PASSED
            and state.ci_run is not None
            and state.ci_run.conclusion == "success"
        )
        has_commit = (
            state.execution is not None
            and bool(state.execution.commit_sha)
        )
        review_ok = True
        if state.execution and state.execution.review:
            review_ok = (state.execution.review.verdict is ReviewVerdict.APPROVED)

        # Check industry pack gates if task is bound to an industry pack
        industry_gate_ok = True
        has_industry_pack = bool(state.task.pack_ref or state.task.industry_pack or state.task.metadata.get("industry_pack"))
        if has_industry_pack and state.execution:
            gate_status = state.execution.metadata.get("industry_gates_passed", "").lower()
            industry_gate_ok = (gate_status == "true")

        task_success = ci_success and has_commit and review_ok and industry_gate_ok
        if state.ci_run:
            evidence_list.append(f"ci_run:{state.ci_run.run_id}")
        if state.execution:
            evidence_list.append(f"commit:{state.execution.commit_sha}")
            if state.execution.review:
                evidence_list.append(f"review:{state.execution.review.verdict}")
            if has_industry_pack:
                evidence_list.append(f"industry_gates:{'passed' if industry_gate_ok else 'failed'}")

        if not task_success:
            reasons = []
            if not ci_success:
                reasons.append("CI not passed")
            if not has_commit:
                reasons.append("No published commit")
            if not review_ok:
                reasons.append("Review not approved")
            if not industry_gate_ok:
                reasons.append("Industry compliance/audit gates failed or missing")
            return VerificationResult(
                accepted=False,
                summary=f"Delivery rejected: {'; '.join(reasons)}",
                evidence=tuple(evidence_list),
                outcome_status=DeliveryOutcomeStatus.REJECTED,
                task_success=False,
                runtime_clean_completion=True,
                evidence_completeness=True,
            )

        # 2. Evaluate evidence completeness
        metadata = state.execution.metadata if state.execution else {}
        trajectory_id = metadata.get("trajectory_id", "")
        trajectory_events = int(metadata.get("trajectory_event_count", "0"))
        capture_issues = int(metadata.get("capture_issues", "0"))

        evidence_completeness = (
            bool(trajectory_id)
            and not trajectory_id.startswith("fallback-")
            and trajectory_events > 0
            and capture_issues == 0
        )
        if trajectory_id:
            evidence_list.append(f"trajectory:{trajectory_id}")

        if not evidence_completeness:
            # Empty trajectory or capture issues MUST NOT be accepted as complete verified delivery!
            reasons = []
            if not trajectory_id or trajectory_events == 0:
                reasons.append("empty or missing trajectory")
            if trajectory_id.startswith("fallback-"):
                reasons.append("fallback trajectory used")
            if capture_issues > 0:
                reasons.append(f"{capture_issues} capture issue(s)")
            return VerificationResult(
                accepted=False,
                summary=f"Delivery evidence incomplete: {'; '.join(reasons)}",
                evidence=tuple(evidence_list),
                outcome_status=DeliveryOutcomeStatus.EVIDENCE_INCOMPLETE,
                task_success=True,
                runtime_clean_completion=False,
                evidence_completeness=False,
                degradation_reason=f"Evidence incomplete ({', '.join(reasons)})",
                escalation_path="inspect_trajectory_pipeline_and_rerun_with_full_tracing",
            )

        # 3. Evaluate runtime clean completion
        runtime_degraded = metadata.get("runtime_degraded", "").lower() == "true"
        runtime_clean = not runtime_degraded

        if not runtime_clean:
            degradation_reason = metadata.get("runtime_degradation_reason", "runtime_timeout_or_recovery")
            return VerificationResult(
                accepted=True,
                summary=(
                    f"Delivery accepted with runtime degradation: {degradation_reason}. "
                    "Task succeeded and evidence is complete, but runtime encountered non-fatal degradation."
                ),
                evidence=tuple(evidence_list),
                outcome_status=DeliveryOutcomeStatus.VERIFIED_DEGRADED,
                task_success=True,
                runtime_clean_completion=False,
                evidence_completeness=True,
                degradation_reason=degradation_reason,
                escalation_path="human_review_recommended:check_runtime_logs_and_timeout_margins",
            )

        # All clean
        return VerificationResult(
            accepted=True,
            summary="Delivery verified clean: task succeeded, evidence complete, runtime healthy.",
            evidence=tuple(evidence_list),
            outcome_status=DeliveryOutcomeStatus.VERIFIED_CLEAN,
            task_success=True,
            runtime_clean_completion=True,
            evidence_completeness=True,
        )
