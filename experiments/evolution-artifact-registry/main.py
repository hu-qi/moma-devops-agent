"""Credential-free smoke for governed Artifact Registry promotion/rollback."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionEvidence,
    PromotionDecision,
    RollbackDecision,
)
from devopspilot.persistence import (
    ArtifactRegistryConflict,
    SQLiteArtifactRegistry,
)


async def main() -> None:
    db = Path(tempfile.mkdtemp(prefix="devopspilot_artifact_registry_")) / "registry.db"
    registry = SQLiteArtifactRegistry(db)

    baseline = ArtifactVersion(
        artifact_id="skill.build-debug",
        kind=ArtifactKind.SKILL,
        version="1.0.0",
        content="baseline",
    )
    await registry.register_baseline(baseline)

    candidate = EvolutionCandidate(
        candidate_id="candidate-2",
        artifact=ArtifactVersion(
            artifact_id="skill.build-debug",
            kind=ArtifactKind.SKILL,
            version="2.0.0-candidate.1",
            content="candidate",
        ),
        base_artifact_id=baseline.artifact_id,
        base_version=baseline.version,
        provider_id="smoke",
        change_summary="improve",
        source_trajectory_ids=("t1",),
    )
    await registry.stage_candidate(candidate)

    evidence = EvolutionEvidence(
        candidate_id=candidate.candidate_id,
        baseline=(BenchmarkObservation("case-1", True, tool_calls=5),),
        candidate=(BenchmarkObservation("case-1", True, tool_calls=3),),
        improved_metrics=("tool_calls",),
        regressions=(),
        gate_passed=True,
    )

    pending = PromotionDecision(
        candidate_id=candidate.candidate_id,
        state=ApprovalState.PENDING_HUMAN,
        evidence=evidence,
        rollback_version=baseline.version,
    )
    try:
        await registry.promote(candidate, pending, decided_by="human")
    except PermissionError:
        pass
    else:
        raise AssertionError("PENDING_HUMAN candidate must not activate")

    approved = PromotionDecision(
        candidate_id=candidate.candidate_id,
        state=ApprovalState.APPROVED,
        evidence=evidence,
        rollback_version=baseline.version,
        reason="explicit test approval",
    )
    await registry.promote(candidate, approved, decided_by="human")
    assert (await registry.get_active(candidate.artifact.artifact_id)) == candidate.artifact

    await registry.rollback(RollbackDecision(
        artifact_id=baseline.artifact_id,
        target_version=baseline.version,
        state=ApprovalState.APPROVED,
        decided_by="human",
        reason="rollback smoke",
    ))
    assert (await registry.get_active(baseline.artifact_id)) == baseline

    created = EvolutionCandidate(
        candidate_id="candidate-new-team",
        artifact=ArtifactVersion(
            artifact_id="devopspilot-team-swarm",
            kind=ArtifactKind.TEAM_PATTERN,
            version="candidate.1",
            content="new team",
        ),
        base_artifact_id="team-pattern-proposal:x",
        base_version="proposal-v1",
        provider_id="smoke",
        change_summary="new team",
        source_trajectory_ids=("t2",),
    )
    await registry.stage_candidate(created)
    created_evidence = EvolutionEvidence(
        candidate_id=created.candidate_id,
        baseline=(BenchmarkObservation("case-1", True, runtime_clean_completion=False),),
        candidate=(BenchmarkObservation("case-1", True, runtime_clean_completion=True),),
        improved_metrics=("runtime_clean_completion",),
        regressions=(),
        gate_passed=True,
    )
    await registry.promote(
        created,
        PromotionDecision(
            candidate_id=created.candidate_id,
            state=ApprovalState.APPROVED,
            evidence=created_evidence,
            rollback_version="proposal-v1",
            reason="explicit create approval",
        ),
        decided_by="human",
    )
    assert await registry.get_active(created.artifact.artifact_id) is not None

    await registry.rollback(RollbackDecision(
        artifact_id=created.artifact.artifact_id,
        target_version=None,
        state=ApprovalState.APPROVED,
        decided_by="human",
        reason="deactivate newly created artifact",
    ))
    assert await registry.get_active(created.artifact.artifact_id) is None

    history = await registry.activation_history(baseline.artifact_id)
    assert [row["action"] for row in history] == ["promote", "rollback"]

    conflicting = ArtifactVersion(
        artifact_id=baseline.artifact_id,
        kind=baseline.kind,
        version=baseline.version,
        content="different",
    )
    try:
        await registry.register_baseline(conflicting)
    except ArtifactRegistryConflict:
        pass
    else:
        raise AssertionError("artifact version identity must be immutable")

    print("ARTIFACT_REGISTRY_STAGING_OK")
    print("ARTIFACT_REGISTRY_PENDING_BLOCKED_OK")
    print("ARTIFACT_REGISTRY_PROMOTION_OK")
    print("ARTIFACT_REGISTRY_ROLLBACK_OK")
    print("ARTIFACT_REGISTRY_DEACTIVATION_OK")
    print("ARTIFACT_REGISTRY_IMMUTABLE_VERSION_OK")


if __name__ == "__main__":
    asyncio.run(main())
