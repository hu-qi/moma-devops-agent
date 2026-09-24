"""Live sandbox Team Pattern -> Swarm Skill candidate generation."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from devopspilot.adapters.jiuwenswarm import (
    JiuwenSwarmSkillCandidateProvider,
    materialize_swarm_skill_candidate,
)
from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    TeamPatternCreationDecision,
    TeamPatternCreationProposal,
)
from devopspilot.persistence.evolution_audit import SQLiteEvolutionAuditStore


ROOT = Path(__file__).resolve().parents[2]


async def main() -> None:
    creator_root = Path(os.environ["JIUWENSWARM_CREATOR_ROOT"]).resolve()
    creator_ref = os.environ["JIUWENSWARM_CREATOR_REF"].strip()

    proposal = TeamPatternCreationProposal(
        proposal_id="synthetic-team-pattern-proposal-ci",
        proposal_key="devopspilot-team-runtime-agentteam-timeout",
        reusable_guidance=(
            "Create a reusable DevOps delivery Team/Swarm Skill that defines "
            "Leader, Coding, and Review collaboration; explicit task dependency "
            "and completion criteria; bounded member shutdown/timeout handling; "
            "independent verification before delivery; and a deterministic "
            "handoff from member completion to Leader finalization."
        ),
        evidence=(
            "trajectory-a: task correct, AgentTeam stream timed out after Coding and Review completed.",
            "trajectory-b: GitHub delivery verified, AgentTeam stream timed out during team finalization.",
        ),
        source_opportunity_ids=(
            "team-pattern:bench:agentteam_timeout",
            "team-pattern:github-e2e:agentteam_timeout",
        ),
        provider_id="openjiuwen-team-skill-create",
        approval_payload={"synthetic": True},
        production_write=False,
    )
    approved = TeamPatternCreationDecision(
        proposal_id=proposal.proposal_id,
        state=ApprovalState.APPROVED,
        decided_by="synthetic-ci",
        reason="Exercise the governed sandbox creation pipeline only.",
    )

    provider = JiuwenSwarmSkillCandidateProvider(
        creator_root=creator_root,
        creator_ref=creator_ref,
    )

    # Governance negative gate: non-approved proposals cannot invoke the creator.
    pending = TeamPatternCreationDecision(
        proposal_id=proposal.proposal_id,
        state=ApprovalState.PENDING_HUMAN,
        decided_by="synthetic-ci",
        reason="negative gate",
    )
    try:
        await provider.generate_candidate(proposal, pending)
    except PermissionError:
        pass
    else:
        raise AssertionError("pending proposal unexpectedly generated a candidate")

    with tempfile.TemporaryDirectory(prefix="devopspilot_team_candidate_audit_") as td:
        audit = SQLiteEvolutionAuditStore(Path(td) / "evolution.sqlite3")
        await audit.save_team_pattern_proposal(proposal)
        stored_decision = await audit.append_team_pattern_creation_decision(approved)
        assert stored_decision.version == 1
        assert stored_decision.decision.state is ApprovalState.APPROVED

        candidate = await provider.generate_candidate(proposal, approved)
        assert candidate.artifact.kind is ArtifactKind.TEAM_PATTERN
        assert candidate.metadata["official_validator"] == "passed"
        assert candidate.metadata["production_write"] is False
        assert candidate.metadata["creator_ref"] == creator_ref

        await audit.save_candidate(candidate)
        loaded = await audit.load_candidate(candidate.candidate_id)
        assert loaded == candidate

        artifacts = ROOT / "artifacts"
        artifacts.mkdir(exist_ok=True)
        bundle_path = artifacts / "team-pattern-candidate.json"
        bundle_path.write_text(candidate.artifact.content, encoding="utf-8")

        materialized_root = artifacts / "team-pattern-candidate"
        if materialized_root.exists():
            import shutil
            shutil.rmtree(materialized_root)
        materialized_root.mkdir(parents=True)
        candidate_dir = await materialize_swarm_skill_candidate(
            candidate,
            target_root=materialized_root,
        )

        summary = {
            "candidate_id": candidate.candidate_id,
            "artifact_id": candidate.artifact.artifact_id,
            "artifact_version": candidate.artifact.version,
            "creator_ref": creator_ref,
            "creator_model": candidate.metadata.get("creator_model"),
            "official_validator": candidate.metadata.get("official_validator"),
            "production_write": candidate.metadata.get("production_write"),
            "candidate_dir": str(candidate_dir.relative_to(ROOT)),
        }
        (artifacts / "team-pattern-candidate-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print("TEAM_PATTERN_APPROVAL_GATE_OK")
        print("JIUWENSWARM_CREATOR_TOOL_CALL_OK")
        print("JIUWENSWARM_OFFICIAL_VALIDATOR_OK")
        print("TEAM_PATTERN_CANDIDATE_AUDIT_OK")
        print("TEAM_PATTERN_PRODUCTION_WRITE_FALSE")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
