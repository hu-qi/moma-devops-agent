"""Evolution orchestration with an explicit human promotion boundary."""

from __future__ import annotations

from devopspilot.contracts.evolution import (
    ApprovalState,
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionEvidence,
    EvolutionProvider,
    EvolutionRequest,
    PromotionDecision,
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
        return PromotionDecision(
            candidate_id=candidate.candidate_id,
            state=ApprovalState.PENDING_HUMAN,
            evidence=evidence,
            rollback_version=candidate.base_version,
            reason=(
                "Candidate passed the automated gate and requires explicit "
                "human approval before production promotion."
                if evidence.gate_passed
                else "Candidate failed the automated gate and is not promotable."
            ),
        )
