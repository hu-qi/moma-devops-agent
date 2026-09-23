"""Credential-free smoke for governed evolution contracts and gate."""

from __future__ import annotations

import asyncio

from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionRequest,
)
from devopspilot.evolution import EvolutionEngine


class FakeEvolutionProvider:
    provider_id = "fake-evolution"

    async def generate_candidate(self, request: EvolutionRequest) -> EvolutionCandidate:
        candidate = ArtifactVersion(
            artifact_id=request.base_artifact.artifact_id,
            kind=request.base_artifact.kind,
            version="2.0.0-candidate.1",
            content=request.base_artifact.content + "\nPre-check CI working directory before retry.\n",
        )
        return EvolutionCandidate(
            candidate_id="build-debug-v2-c1",
            artifact=candidate,
            base_artifact_id=request.base_artifact.artifact_id,
            base_version=request.base_artifact.version,
            provider_id=self.provider_id,
            change_summary="Add deterministic working-directory pre-check.",
            source_trajectory_ids=request.source_trajectory_ids,
        )


async def main() -> None:
    base = ArtifactVersion(
        artifact_id="skill.build-debug",
        kind=ArtifactKind.SKILL,
        version="1.0.0",
        content="Inspect failing logs and retry the failed build.",
    )
    request = EvolutionRequest(
        request_id="evolve-build-debug-1",
        base_artifact=base,
        objective="Improve CI-debug success with fewer wasted tool calls.",
        source_trajectory_ids=("trajectory-ci-001", "trajectory-ci-002"),
        evaluation_cases=(
            "ci.python.wrong_working_directory.001",
            "ci.python.dependency_resolution.001",
        ),
    )
    engine = EvolutionEngine(provider=FakeEvolutionProvider())
    candidate = await engine.propose(request)

    baseline = (
        BenchmarkObservation(
            case_id="ci.python.wrong_working_directory.001",
            task_success=False,
            tool_calls=10,
            input_tokens=3000,
            output_tokens=800,
            duration_ms=9000,
        ),
        BenchmarkObservation(
            case_id="ci.python.dependency_resolution.001",
            task_success=True,
            tool_calls=8,
            input_tokens=2500,
            output_tokens=700,
            duration_ms=7000,
        ),
    )
    candidate_results = (
        BenchmarkObservation(
            case_id="ci.python.wrong_working_directory.001",
            task_success=True,
            tool_calls=5,
            input_tokens=1800,
            output_tokens=500,
            duration_ms=5000,
        ),
        BenchmarkObservation(
            case_id="ci.python.dependency_resolution.001",
            task_success=True,
            tool_calls=6,
            input_tokens=2100,
            output_tokens=600,
            duration_ms=6000,
        ),
    )

    evidence = engine.evaluate(
        request=request,
        candidate=candidate,
        baseline=baseline,
        candidate_results=candidate_results,
    )
    assert evidence.gate_passed is True
    assert "task_success" in evidence.improved_metrics
    assert not evidence.regressions

    decision = engine.await_human_approval(
        candidate=candidate,
        evidence=evidence,
    )
    assert decision.state is ApprovalState.PENDING_HUMAN
    assert decision.rollback_version == "1.0.0"

    regressed = list(candidate_results)
    regressed[1] = BenchmarkObservation(
        case_id="ci.python.dependency_resolution.001",
        task_success=False,
    )
    bad = engine.evaluate(
        request=request,
        candidate=candidate,
        baseline=baseline,
        candidate_results=tuple(regressed),
    )
    assert bad.gate_passed is False
    assert "ci.python.dependency_resolution.001:task-success" in bad.regressions
    rejected = engine.await_human_approval(
        candidate=candidate,
        evidence=bad,
    )
    assert rejected.state is ApprovalState.REJECTED

    print("EVOLUTION_FAILED_GATE_REJECTED_OK")
    print("EVOLUTION_CONTRACT_OK")
    print("EVOLUTION_CANDIDATE_VERSIONING_OK")
    print("DEVOPSBENCH_REGRESSION_GATE_OK")
    print("HUMAN_PROMOTION_BOUNDARY_OK")
    print("ROLLBACK_TARGET_OK")


if __name__ == "__main__":
    asyncio.run(main())
