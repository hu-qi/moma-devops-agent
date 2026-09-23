"""Smoke-test immutable/versioned evolution audit persistence."""

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
    TeamPatternCreationProposal,
)
from devopspilot.persistence import EvolutionAuditConflict, SQLiteEvolutionAuditStore


async def main() -> None:
    path = Path(tempfile.mkdtemp(prefix="devopspilot_evolution_audit_")) / "audit.db"
    store = SQLiteEvolutionAuditStore(path)

    proposal = TeamPatternCreationProposal(
        proposal_id="team-proposal-1",
        proposal_key="devopspilot-team-runtime-agentteam-timeout",
        reusable_guidance=(
            "Create a reusable DevOps Team/Swarm Skill with explicit completion "
            "and timeout handling."
        ),
        evidence=("trajectory-a: timeout", "trajectory-b: timeout"),
        source_opportunity_ids=("op-a", "op-b"),
        provider_id="openjiuwen-team-skill-create",
        approval_payload={
            "request_id": "team-proposal-1",
            "questions": [{"question": "Create Team/Swarm Skill?"}],
        },
        production_write=False,
    )
    await store.save_team_pattern_proposal(proposal)
    loaded_proposal = await store.load_team_pattern_proposal("team-proposal-1")
    assert loaded_proposal == proposal

    conflicting_proposal = TeamPatternCreationProposal(
        proposal_id="team-proposal-1",
        proposal_key=proposal.proposal_key,
        reusable_guidance="different guidance under same immutable proposal id",
        evidence=proposal.evidence,
        source_opportunity_ids=proposal.source_opportunity_ids,
        provider_id=proposal.provider_id,
        approval_payload=proposal.approval_payload,
        production_write=False,
    )
    try:
        await store.save_team_pattern_proposal(conflicting_proposal)
    except EvolutionAuditConflict:
        pass
    else:
        raise AssertionError("team pattern proposal identity must be immutable")

    candidate = EvolutionCandidate(
        candidate_id="candidate-1",
        artifact=ArtifactVersion(
            artifact_id="skill.build-debug.experience",
            kind=ArtifactKind.SKILL_EXPERIENCE,
            version="1.0.0-candidate.a1",
            content='{"records":[{"id":"ev_1"}]}',
        ),
        base_artifact_id="skill.build-debug.experience",
        base_version="1.0.0",
        provider_id="openjiuwen-skill-evolution",
        change_summary="Check CI working directory before repair.",
        source_trajectory_ids=("trajectory-1",),
    )
    await store.save_candidate(candidate)
    loaded = await store.load_candidate("candidate-1")
    assert loaded == candidate

    evidence = EvolutionEvidence(
        candidate_id="candidate-1",
        baseline=(
            BenchmarkObservation(
                case_id="ci.github_actions.working_directory.001",
                task_success=False,
                tool_calls=10,
            ),
        ),
        candidate=(
            BenchmarkObservation(
                case_id="ci.github_actions.working_directory.001",
                task_success=True,
                tool_calls=6,
            ),
        ),
        improved_metrics=("task_success", "tool_calls"),
        regressions=(),
        gate_passed=True,
    )
    e1 = await store.append_evidence(evidence)
    e2 = await store.append_evidence(evidence)
    assert (e1.version, e2.version) == (1, 2)
    assert (await store.load_latest_evidence("candidate-1")).version == 2

    pending = PromotionDecision(
        candidate_id="candidate-1",
        state=ApprovalState.PENDING_HUMAN,
        evidence=evidence,
        rollback_version="1.0.0",
        reason="Awaiting explicit human approval.",
    )
    d1 = await store.append_decision(pending)
    assert d1.version == 1
    assert (await store.load_latest_decision("candidate-1")).decision.state is ApprovalState.PENDING_HUMAN

    bad_evidence = EvolutionEvidence(
        candidate_id="candidate-1",
        baseline=evidence.baseline,
        candidate=(
            BenchmarkObservation(
                case_id="ci.github_actions.working_directory.001",
                task_success=False,
            ),
        ),
        improved_metrics=(),
        regressions=("ci.github_actions.working_directory.001:task-success",),
        gate_passed=False,
    )
    invalid_approval = PromotionDecision(
        candidate_id="candidate-1",
        state=ApprovalState.APPROVED,
        evidence=bad_evidence,
        rollback_version="1.0.0",
    )
    try:
        await store.append_decision(invalid_approval)
    except EvolutionAuditConflict:
        pass
    else:
        raise AssertionError("failed-gate candidate must never be recorded APPROVED")

    conflicting = EvolutionCandidate(
        candidate_id="candidate-1",
        artifact=candidate.artifact,
        base_artifact_id=candidate.base_artifact_id,
        base_version=candidate.base_version,
        provider_id=candidate.provider_id,
        change_summary="Different content under the same immutable candidate id.",
        source_trajectory_ids=candidate.source_trajectory_ids,
    )
    try:
        await store.save_candidate(conflicting)
    except EvolutionAuditConflict:
        pass
    else:
        raise AssertionError("candidate identity must be immutable")

    print("EVOLUTION_AUDIT_TEAM_PATTERN_PROPOSAL_IMMUTABLE_OK")
    print("EVOLUTION_AUDIT_CANDIDATE_IMMUTABLE_OK")
    print("EVOLUTION_AUDIT_EVIDENCE_VERSIONED_OK")
    print("EVOLUTION_AUDIT_DECISION_VERSIONED_OK")
    print("EVOLUTION_AUDIT_FAILED_GATE_APPROVAL_BLOCKED_OK")


if __name__ == "__main__":
    asyncio.run(main())
