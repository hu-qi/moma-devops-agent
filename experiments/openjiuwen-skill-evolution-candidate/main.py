"""Live candidate-only OpenJiuwen Skill evolution smoke."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from devopspilot.adapters.openjiuwen import OpenJiuwenSkillEvolutionProvider
from devopspilot.contracts.evolution import (
    ArtifactKind,
    ArtifactVersion,
    EvolutionRequest,
    EvolutionSignalEvidence,
)
from devopspilot.evolution import EvolutionEngine


ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = ROOT / "skills"
PRODUCTION_LOG = SKILLS_ROOT / "build-debug" / "evolutions.json"
ARTIFACT_DIR = ROOT / "artifacts"


async def main() -> None:
    if PRODUCTION_LOG.exists():
        raise RuntimeError(
            "Production build-debug evolutions.json must not exist before "
            "candidate-only evolution smoke"
        )

    base = ArtifactVersion(
        artifact_id="skill.build-debug.experience",
        kind=ArtifactKind.SKILL_EXPERIENCE,
        version="1.0.0",
        content=json.dumps(
            {
                "format": "devopspilot.skill-experience/v1",
                "skill_name": "build-debug",
                "records": [],
            },
            sort_keys=True,
        ),
        metadata={"skill_name": "build-debug"},
    )
    request = EvolutionRequest(
        request_id="build-debug-wrong-working-directory-v1",
        base_artifact=base,
        objective=(
            "Improve build-debug so an agent verifies the CI command execution "
            "directory and workflow working-directory before changing code, "
            "dependencies, or blindly retrying a failed build."
        ),
        source_trajectory_ids=(
            "devopsbench:ci.python.wrong_working_directory.001:baseline",
        ),
        evaluation_cases=(
            "ci.python.wrong_working_directory.001",
        ),
        signals=(
            EvolutionSignalEvidence(
                signal_type="execution_failure",
                section="Troubleshooting",
                excerpt=(
                    "The CI job failed because the test command was executed "
                    "from the repository root while the Python service lived "
                    "under service/. The correct repair is to inspect the "
                    "workflow execution context and working-directory before "
                    "changing dependencies or application code."
                ),
                source="devopsbench",
                trajectory_id=(
                    "devopsbench:ci.python.wrong_working_directory.001:baseline"
                ),
                tool_name="ci-log",
                metadata={
                    "case_id": "ci.python.wrong_working_directory.001",
                    "failure_class": "wrong-working-directory",
                },
            ),
        ),
    )

    engine = EvolutionEngine(
        provider=OpenJiuwenSkillEvolutionProvider(
            skills_root=SKILLS_ROOT,
            language="en",
        )
    )
    candidate = await engine.propose(request)

    payload = json.loads(candidate.artifact.content)
    assert payload["skill_name"] == "build-debug"
    assert payload["records"]
    assert candidate.metadata["sandboxed"] is True
    assert candidate.metadata["production_write"] is False
    assert candidate.metadata["record_count"] == len(payload["records"])

    if PRODUCTION_LOG.exists():
        raise RuntimeError(
            "Candidate generation mutated production build-debug evolution state"
        )

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "build-debug-skill-experience-candidate.json"
    output.write_text(
        json.dumps(
            {
                "candidate_id": candidate.candidate_id,
                "base_artifact_id": candidate.base_artifact_id,
                "base_version": candidate.base_version,
                "provider_id": candidate.provider_id,
                "change_summary": candidate.change_summary,
                "source_trajectory_ids": list(candidate.source_trajectory_ids),
                "metadata": dict(candidate.metadata),
                "artifact": {
                    "artifact_id": candidate.artifact.artifact_id,
                    "kind": candidate.artifact.kind.value,
                    "version": candidate.artifact.version,
                    "digest": candidate.artifact.digest,
                    "content": payload,
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print("OPENJIUWEN_SKILL_EVOLUTION_STAGED_OK")
    print("EVOLUTION_SANDBOX_ISOLATION_OK")
    print("EVOLUTION_PRODUCTION_WRITE_FALSE_OK")
    print(f"EVOLUTION_CANDIDATE_ID={candidate.candidate_id}")
    print(f"EVOLUTION_RECORD_COUNT={candidate.metadata['record_count']}")
    print(f"EVOLUTION_MODEL={candidate.metadata['openjiuwen_model']}")
    print("EVOLUTION_CHANGE_SUMMARY=" + candidate.change_summary[:1200])


if __name__ == "__main__":
    asyncio.run(main())
