"""Stage a governed Team/Swarm Skill creation proposal from real repeated evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from devopspilot.adapters.openjiuwen import OpenJiuwenTeamSkillCreationProvider
from devopspilot.contracts.evolution import (
    ArtifactKind,
    EvolutionOpportunity,
    EvolutionSignalEvidence,
    OpportunityPriority,
)


ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "skills"
ARTIFACT_DIR = ROOT / "artifacts"


def snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def opportunity(
    *,
    opportunity_id: str,
    trajectory_id: str,
    source: str,
    detail: str,
) -> EvolutionOpportunity:
    return EvolutionOpportunity(
        opportunity_id=opportunity_id,
        target_kind=ArtifactKind.TEAM_PATTERN,
        objective=(
            "Improve AgentTeam completion and termination behavior without "
            "reducing task correctness, review independence, or deterministic verification."
        ),
        source_trajectory_ids=(trajectory_id,),
        signals=(
            EvolutionSignalEvidence(
                signal_type="runtime_degradation",
                section="AgentTeam Runtime",
                excerpt=detail,
                source=source,
                trajectory_id=trajectory_id,
                metadata={
                    "task_success": "true",
                    "runtime_clean_completion": "false",
                    "runtime_degradation_reason": "agentteam_timeout",
                },
            ),
        ),
        priority=OpportunityPriority.HIGH,
        auto_candidate_allowed=True,
    )


async def main() -> None:
    before = snapshot(SKILLS_ROOT)

    evidence = (
        opportunity(
            opportunity_id="team-pattern:devopsbench:agentteam-timeout",
            trajectory_id="df3bf8ab84422c053ad951c8e704b7f3",
            source="devopsbench-task-executor",
            detail=(
                "The coding/review team produced a correct patch, passed independent "
                "tests and DevOpsBench, but the OpenJiuwen AgentTeam stream did not "
                "terminate cleanly within 180 seconds."
            ),
        ),
        opportunity(
            opportunity_id="team-pattern:github-e2e:agentteam-timeout",
            trajectory_id="df43e104d607bd752c1d8f8d13475da5",
            source="github-live-delivery-e2e",
            detail=(
                "The live GitHub delivery produced the exact allowed one-file patch, "
                "published commit fb2e70b74f16859afa5ee2f015ef9e8c864353fb, "
                "and passed GitHub Actions, while the AgentTeam stream again required "
                "timeout degradation handling."
            ),
        ),
    )

    provider = OpenJiuwenTeamSkillCreationProvider(
        skills_root=SKILLS_ROOT,
        language="en",
    )
    proposal = await provider.propose_creation(evidence)

    after = snapshot(SKILLS_ROOT)
    assert before == after, "production skills changed during proposal staging"
    assert proposal.production_write is False
    assert proposal.provider_id == "openjiuwen-team-skill-create"
    assert len(proposal.evidence) == 2
    assert proposal.proposal_key == "devopspilot-team-runtime-agentteam-timeout"
    assert proposal.approval_payload.get("request_id") == proposal.proposal_id

    questions = proposal.approval_payload.get("questions") or []
    assert len(questions) == 1
    assert "Team/Swarm Skill" in str(questions[0].get("question", ""))

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "team-pattern-creation-proposal.json"
    output.write_text(
        json.dumps(
            {
                "proposal_id": proposal.proposal_id,
                "proposal_key": proposal.proposal_key,
                "provider_id": proposal.provider_id,
                "reusable_guidance": proposal.reusable_guidance,
                "evidence": list(proposal.evidence),
                "source_opportunity_ids": list(proposal.source_opportunity_ids),
                "approval_payload": dict(proposal.approval_payload),
                "production_write": proposal.production_write,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("TEAM_PATTERN_REPEAT_EVIDENCE_OK")
    print("OPENJIUWEN_TEAM_SKILL_CREATE_PROPOSAL_OK")
    print("TEAM_SKILL_APPROVAL_EVENT_OK")
    print("TEAM_SKILL_PRODUCTION_WRITE_FALSE_OK")
    print(f"TEAM_SKILL_PROPOSAL_ID={proposal.proposal_id}")
    print(f"TEAM_SKILL_PROPOSAL_KEY={proposal.proposal_key}")


if __name__ == "__main__":
    asyncio.run(main())
