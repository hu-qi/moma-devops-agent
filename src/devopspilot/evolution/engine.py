"""Evolution orchestration with an explicit human promotion boundary."""

from __future__ import annotations

from devopspilot.contracts.evolution import (
    ApprovalState,
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionEvidence,
    EvolutionProvider,
    EvolutionRequest,
    HumanPromotionApproval,
    PromotionDecision,
    RollbackDecision,
    UnauthorizedPromotionError,
)

from .gate import RegressionGate


class EvolutionEngine:
    def __init__(
        self,
        *,
        provider: EvolutionProvider,
        gate: RegressionGate | None = None,
    ) -> None:
        self._provider = provider
        self._gate = gate or RegressionGate()

    async def propose(self, request: EvolutionRequest) -> EvolutionCandidate:
        candidate = await self._provider.generate_candidate(request)
        if candidate.base_artifact_id != request.base_artifact.artifact_id:
            raise RuntimeError("Evolution provider changed base artifact identity")
        if candidate.base_version != request.base_artifact.version:
            raise RuntimeError("Evolution provider changed base artifact version")
        if candidate.artifact.digest == request.base_artifact.digest:
            raise RuntimeError("Evolution provider returned an unchanged candidate")
        return candidate

    def evaluate(
        self,
        *,
        request: EvolutionRequest,
        candidate: EvolutionCandidate,
        baseline: tuple[BenchmarkObservation, ...],
        candidate_results: tuple[BenchmarkObservation, ...],
    ) -> EvolutionEvidence:
        return self._gate.evaluate(
            request=request,
            candidate=candidate,
            baseline=baseline,
            candidate_results=candidate_results,
        )

    @staticmethod
    def await_human_approval(
        *,
        candidate: EvolutionCandidate,
        evidence: EvolutionEvidence,
    ) -> PromotionDecision:
        if not evidence.gate_passed:
            return PromotionDecision(
                candidate_id=candidate.candidate_id,
                state=ApprovalState.REJECTED,
                evidence=evidence,
                rollback_version=candidate.base_version,
                reason="Candidate failed the automated gate and is not promotable.",
            )

        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            state=ApprovalState.PENDING_HUMAN,
            evidence=evidence,
            rollback_version=candidate.base_version,
            reason=(
                "Candidate passed the automated gate and requires explicit "
                "human approval before production promotion."
            ),
        )

    @staticmethod
    def promote_to_production(
        *,
        decision: PromotionDecision,
        approval: HumanPromotionApproval,
    ) -> PromotionDecision:
        if decision.state != ApprovalState.PENDING_HUMAN:
            raise ValueError(f"Cannot promote decision with state {decision.state}")

        if approval.synthetic and approval.production:
            raise UnauthorizedPromotionError(
                "Synthetic or mock approvals are strictly prohibited from promoting to production; "
                "an explicit verified human sign-off is required."
            )

        if not approval.sign_off:
            return PromotionDecision(
                candidate_id=decision.candidate_id,
                state=ApprovalState.REJECTED,
                evidence=decision.evidence,
                rollback_version=decision.rollback_version,
                reason=f"Human reviewer rejected promotion: {approval.notes}",
            )

        return PromotionDecision(
            candidate_id=decision.candidate_id,
            state=ApprovalState.APPROVED,
            evidence=decision.evidence,
            rollback_version=decision.rollback_version,
            reason=f"Promoted to production by {approval.approver}: {approval.notes}",
        )

    @staticmethod
    def rollback(
        *,
        artifact_id: str,
        target_version: str,
        decided_by: str,
        reason: str = "",
    ) -> RollbackDecision:
        return RollbackDecision(
            artifact_id=artifact_id,
            target_version=target_version,
            state=ApprovalState.APPROVED,
            decided_by=decided_by,
            reason=reason or f"Rollback to version {target_version} authorized by {decided_by}",
        )
