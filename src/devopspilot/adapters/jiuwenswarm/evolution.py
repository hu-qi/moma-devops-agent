"""Sandbox Swarm Skill candidate generation using JiuwenSwarm creator rules."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    EvolutionCandidate,
    TeamPatternCreationDecision,
    TeamPatternCreationProposal,
)


_FORMAT = "devopspilot.swarm-skill-bundle/v1"
_REQUIRED_FILES = {"SKILL.md", "workflow.md", "bind.md", "dependencies.yaml"}


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _candidate_name(proposal: TeamPatternCreationProposal) -> str:
    value = proposal.proposal_key.lower().strip()
    value = value.removeprefix("devopspilot-team-runtime-")
    value = re.sub(r"[^a-z0-9-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    if not value:
        value = "delivery-team"
    name = f"devopspilot-{value}-swarm"
    return name[:80].rstrip("-")


def _validate_bundle_shape(name: str, files: list[dict[str, Any]]) -> None:
    if not files:
        raise ValueError("Swarm Skill candidate contains no files")

    seen: set[str] = set()
    role_files: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("candidate file entries must be objects")
        raw_path = str(item.get("path", "")).strip()
        content = item.get("content")
        if not raw_path or not isinstance(content, str) or not content.strip():
            raise ValueError("candidate file requires non-empty path/content")

        path = PurePosixPath(raw_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe candidate path: {raw_path}")
        normalized = path.as_posix()
        if normalized in seen:
            raise ValueError(f"duplicate candidate path: {normalized}")
        seen.add(normalized)

        if normalized.startswith("roles/") and normalized.endswith(".md"):
            if len(path.parts) != 2:
                raise ValueError(f"nested role path is unsupported: {normalized}")
            role_files.add(normalized)
            continue

        if normalized not in _REQUIRED_FILES:
            raise ValueError(
                "V1 Team Pattern candidate only permits the full Markdown "
                f"Swarm Skill shape; unexpected file: {normalized}"
            )

    missing = _REQUIRED_FILES - seen
    if missing:
        raise ValueError(
            "Swarm Skill candidate missing required files: "
            + ", ".join(sorted(missing))
        )
    if len(role_files) < 3:
        raise ValueError(
            "DevOpsPilot delivery Team Pattern requires at least three role files"
        )

    skill_md = next(item["content"] for item in files if item["path"] == "SKILL.md")
    if f"name: {name}" not in skill_md and f'name: "{name}"' not in skill_md:
        raise ValueError(
            f"SKILL.md frontmatter must use deterministic candidate name {name!r}"
        )


async def materialize_swarm_skill_candidate(
    candidate: EvolutionCandidate,
    *,
    target_root: str | Path,
) -> Path:
    if candidate.artifact.kind is not ArtifactKind.TEAM_PATTERN:
        raise ValueError("candidate is not a TEAM_PATTERN artifact")

    payload = json.loads(candidate.artifact.content)
    if payload.get("format") != _FORMAT:
        raise ValueError("unsupported Swarm Skill candidate bundle format")

    name = str(payload.get("name", "")).strip()
    files = payload.get("files")
    if not name or not isinstance(files, list):
        raise ValueError("invalid Swarm Skill candidate bundle")
    _validate_bundle_shape(name, files)

    root = Path(target_root).resolve()
    destination = root / name
    if destination.exists():
        raise FileExistsError(f"candidate destination already exists: {destination}")
    destination.mkdir(parents=True)

    for item in files:
        path = destination / PurePosixPath(item["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item["content"], encoding="utf-8")

    return destination


class JiuwenSwarmSkillCandidateProvider:
    """Generate and validate a sandbox Swarm Skill candidate.

    JiuwenSwarm's swarmskill-creator directory is an external runtime dependency.
    Its SKILL.md is used as the authoritative authoring specification and its
    validate_swarmskill.py script is the acceptance validator.

    The provider never writes to DevOpsPilot's production skills/ directory.
    """

    provider_id = "jiuwenswarm-swarmskill-creator"

    def __init__(
        self,
        *,
        creator_root: str | Path,
        model_name: str | None = None,
        creator_ref: str = "",
    ) -> None:
        self._creator_root = Path(creator_root).resolve()
        self._model_name = model_name
        self._creator_ref = creator_ref

    def _build_model(self):
        from openjiuwen.core.foundation.llm import (
            Model,
            ModelClientConfig,
            ModelRequestConfig,
        )

        model_name = (
            self._model_name
            or os.getenv("MOMA_EVOLUTION_MODEL", "").strip()
            or os.getenv("MOMA_REASONING_MODEL", "").strip()
            or _required_env("MOMA_MODEL")
        )
        return (
            Model(
                model_client_config=ModelClientConfig(
                    client_provider="OpenAI",
                    api_base=_required_env("MOMA_API_BASE"),
                    api_key=_required_env("MOMA_API_KEY"),
                    endpoint_profile="openai_compatible",
                    timeout=240,
                ),
                model_config=ModelRequestConfig(
                    model=model_name,
                    temperature=0,
                ),
            ),
            model_name,
        )

    async def generate_candidate(
        self,
        proposal: TeamPatternCreationProposal,
        decision: TeamPatternCreationDecision,
    ) -> EvolutionCandidate:
        if decision.proposal_id != proposal.proposal_id:
            raise ValueError("creation decision does not match proposal")
        if decision.state is not ApprovalState.APPROVED:
            raise PermissionError(
                "Team Pattern candidate generation requires explicit approval"
            )
        if proposal.production_write:
            raise ValueError("creation proposal unexpectedly indicates production write")

        creator_spec_path = self._creator_root / "SKILL.md"
        validator_path = self._creator_root / "scripts" / "validate_swarmskill.py"
        if not creator_spec_path.is_file():
            raise FileNotFoundError(f"JiuwenSwarm creator spec missing: {creator_spec_path}")
        if not validator_path.is_file():
            raise FileNotFoundError(f"JiuwenSwarm validator missing: {validator_path}")

        creator_spec = creator_spec_path.read_text(encoding="utf-8")
        name = _candidate_name(proposal)
        model, model_name = self._build_model()

        tool = {
            "type": "function",
            "function": {
                "name": "emit_swarm_skill_candidate",
                "description": (
                    "Submit the complete Swarm Skill candidate as files. "
                    "Do not omit required files."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "files": {
                            "type": "array",
                            "minItems": 7,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["path", "content"],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": ["files"],
                    "additionalProperties": False,
                },
            },
        }

        evidence = "\n".join(f"- {item}" for item in proposal.evidence)
        prompt = f"""
You are generating a sandbox candidate only. Follow the authoritative
JiuwenSwarm swarmskill-creator specification below.

Operation: CREATE
Output shape: full Markdown spec, NO scripts/workflow.py.
Candidate directory/name MUST be: {name}

DevOpsPilot approved proposal:
{proposal.reusable_guidance}

Evidence:
{evidence}

Mandatory DevOpsPilot constraints:
- Use exactly the reusable delivery roles Leader, Coding, and Review at minimum.
- Preserve independent Review; Coding and Review must not collapse into one role.
- workflow.md must have explicit task dependencies and deterministic completion.
- bind.md must define bounded teammate timeout/shutdown handling and degraded mode.
- Independent repository verification remains outside the team and cannot be removed.
- dependencies.yaml must explicitly contain both skills and tools segments.
- Do not write production files or claim this candidate is promoted.
- Return the candidate ONLY by calling emit_swarm_skill_candidate.

AUTHORITATIVE CREATOR SPEC:
{creator_spec}
""".strip()

        response = await model.invoke(
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
        )
        calls = [
            call for call in (response.tool_calls or [])
            if getattr(call, "name", "") == "emit_swarm_skill_candidate"
        ]
        if len(calls) != 1:
            raise RuntimeError(
                "creator model did not emit exactly one Swarm Skill candidate tool call"
            )

        arguments = json.loads(calls[0].arguments)
        files = arguments.get("files")
        if not isinstance(files, list):
            raise RuntimeError("creator tool call did not contain files")
        _validate_bundle_shape(name, files)

        payload = {
            "format": _FORMAT,
            "name": name,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        content = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )

        provisional = EvolutionCandidate(
            candidate_id="pending",
            artifact=ArtifactVersion(
                artifact_id=name,
                kind=ArtifactKind.TEAM_PATTERN,
                version="candidate",
                content=content,
                metadata={"candidate_format": _FORMAT},
            ),
            base_artifact_id=f"team-pattern-proposal:{proposal.proposal_id}",
            base_version="proposal-v1",
            provider_id=self.provider_id,
            change_summary=(
                "Generated a sandbox Swarm Skill candidate from an explicitly "
                "approved repeated AgentTeam collaboration proposal."
            ),
            source_trajectory_ids=tuple(
                sorted({
                    item.split(":", 1)[0]
                    for item in proposal.evidence
                    if ":" in item
                })
            ),
        )
        digest = provisional.artifact.digest
        candidate = EvolutionCandidate(
            candidate_id=f"{proposal.proposal_id}:{digest[:12]}",
            artifact=ArtifactVersion(
                artifact_id=name,
                kind=ArtifactKind.TEAM_PATTERN,
                version=f"candidate.{digest[:8]}",
                content=content,
                metadata={
                    "candidate_format": _FORMAT,
                    "creator_ref": self._creator_ref,
                },
            ),
            base_artifact_id=provisional.base_artifact_id,
            base_version=provisional.base_version,
            provider_id=self.provider_id,
            change_summary=provisional.change_summary,
            source_trajectory_ids=provisional.source_trajectory_ids,
            metadata={
                "creator_model": model_name,
                "creator_ref": self._creator_ref,
                "sandboxed": True,
                "production_write": False,
                "approval_decision_by": decision.decided_by,
            },
        )

        with tempfile.TemporaryDirectory(
            prefix="devopspilot_swarmskill_candidate_"
        ) as td:
            candidate_dir = await materialize_swarm_skill_candidate(
                candidate,
                target_root=td,
            )
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(validator_path),
                str(candidate_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            validation_output = (
                stdout.decode("utf-8", errors="replace")
                + stderr.decode("utf-8", errors="replace")
            ).strip()
            if proc.returncode != 0:
                raise RuntimeError(
                    "JiuwenSwarm official validator rejected candidate:\n"
                    + validation_output[-12000:]
                )

        return EvolutionCandidate(
            candidate_id=candidate.candidate_id,
            artifact=candidate.artifact,
            base_artifact_id=candidate.base_artifact_id,
            base_version=candidate.base_version,
            provider_id=candidate.provider_id,
            change_summary=candidate.change_summary,
            source_trajectory_ids=candidate.source_trajectory_ids,
            metadata={
                **dict(candidate.metadata),
                "official_validator": "passed",
            },
        )
