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
_ROLE_IDS = ("leader", "coding", "review")
_ROLE_PURPOSES = {
    "leader": (
        "Orchestrates bounded delivery tasks, dependencies, completion signals, "
        "timeouts, and final handoff."
    ),
    "coding": (
        "Implements the assigned software change and reports completion with "
        "repository evidence."
    ),
    "review": (
        "Independently reviews the Coding output and returns an explicit "
        "approve or request-changes verdict."
    ),
}
_TEMPLATE_BY_FILE = {
    "SKILL.md": "SKILL.md.template",
    "workflow.md": "workflow.md.template",
    "bind.md": "bind.md.template",
    "roles/leader.md": "role.md.template",
    "roles/coding.md": "role.md.template",
    "roles/review.md": "role.md.template",
}


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

    expected_roles = {f"roles/{role_id}.md" for role_id in _ROLE_IDS}
    if role_files != expected_roles:
        raise ValueError(
            "DevOpsPilot V1 Team Pattern candidate requires exactly "
            f"{sorted(expected_roles)}; got {sorted(role_files)}"
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
        file_path = destination / PurePosixPath(item["path"])
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(item["content"], encoding="utf-8")

    return destination


class JiuwenSwarmSkillCandidateProvider:
    """Generate and validate a sandbox Swarm Skill candidate.

    Generation is intentionally staged one file at a time. A previous single
    7-file tool call caused GLM-5.3 to exhaust a 12k-token reasoning budget
    before emitting the structured tool call. Per-file generation makes the
    output contract small, independently bounded, and diagnosable.

    The JiuwenSwarm creator directory remains an external dependency. Its
    official templates constrain each generated file and its validator is the
    final structural acceptance gate. Production skills/ is never written.
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

        # Artifact authoring is a structured-generation task. Prefer an explicit
        # evolution model, then the capability-qualified coding model, and only
        # then the bootstrap/default model.
        model_name = (
            self._model_name
            or os.getenv("MOMA_EVOLUTION_MODEL", "").strip()
            or os.getenv("MOMA_CODING_MODEL", "").strip()
            or _required_env("MOMA_MODEL")
        )
        timeout = float(os.getenv("DEVOPSPILOT_SWARM_FILE_TIMEOUT", "90"))
        return (
            Model(
                model_client_config=ModelClientConfig(
                    client_provider="OpenAI",
                    api_base=_required_env("MOMA_API_BASE"),
                    api_key=_required_env("MOMA_API_KEY"),
                    endpoint_profile="openai_compatible",
                    timeout=timeout,
                ),
                model_config=ModelRequestConfig(
                    model=model_name,
                    temperature=0,
                ),
            ),
            model_name,
        )

    def _template(self, filename: str) -> str:
        path = self._creator_root / "templates" / filename
        if not path.is_file():
            raise FileNotFoundError(f"JiuwenSwarm creator template missing: {path}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _dependencies_content() -> str:
        # This synthetic/sandbox candidate has no separately installed
        # role-specific skills or CLI requirements. Empty explicit segments are
        # validator-compliant and prevent cross-file dependency hallucination.
        return (
            "# DevOpsPilot sandbox candidate dependency manifest\n"
            "# No external role dependency is required for this first A/B.\n"
            "skills: []\n"
            "tools: []\n"
        )

    @staticmethod
    def _common_constraints(
        proposal: TeamPatternCreationProposal,
        name: str,
    ) -> str:
        evidence = "\n".join(f"- {item}" for item in proposal.evidence)
        purposes = "\n".join(
            f"- {role_id}: {_ROLE_PURPOSES[role_id]}"
            for role_id in _ROLE_IDS
        )
        return f"""
Candidate name: {name}
Pattern: specialization pipeline with an isolated independent Review gate.

Approved reusable guidance:
{proposal.reusable_guidance}

Evidence:
{evidence}

Fixed roles and one-line purposes:
{purposes}

Non-negotiable DevOpsPilot constraints:
- Use exactly role ids: leader, coding, review.
- Coding implements. Review independently judges. Leader orchestrates/finalizes.
- Coding and Review MUST NOT collapse into one role.
- External repository verification remains outside this team.
- The Leader cannot declare delivery complete before external verification.
- workflow.md must encode explicit dependencies and deterministic completion.
- bind.md must cover bounded teammate timeout/shutdown and degraded mode.
- SKILL.md role skills/tools are empty lists for this sandbox candidate.
- dependencies.yaml is generated deterministically with skills: [] and tools: [].
- No scripts/workflow.py in this V1 candidate.
- Do not claim promotion or production deployment.
""".strip()

    async def _generate_file(
        self,
        *,
        model: Any,
        model_name: str,
        proposal: TeamPatternCreationProposal,
        name: str,
        path: str,
        template: str,
    ) -> dict[str, str]:
        timeout = float(os.getenv("DEVOPSPILOT_SWARM_FILE_TIMEOUT", "90"))
        max_tokens = int(os.getenv("DEVOPSPILOT_SWARM_FILE_MAX_TOKENS", "4500"))

        role_id = ""
        if path.startswith("roles/"):
            role_id = PurePosixPath(path).stem

        file_rules = {
            "SKILL.md": (
                "Frontmatter name MUST exactly match candidate name; version 0.1; "
                "kind swarm-skill; exactly leader/coding/review roles; each role "
                "kind ai_agent; use the fixed purpose above; skills: [] and tools: []. "
                "Description MUST be exactly three semantic lines WHAT / WHEN / NOT. "
                "Body MUST contain ## Workflow, ## Roles, ## Files. No Mermaid here."
            ),
            "workflow.md": (
                "Use a C-pattern sequential pipeline. Include required Mermaid in "
                "## Overview. Detailed steps MUST explicitly represent Leader planning "
                "-> Coding completion -> Review verdict -> Leader finalization -> "
                "external repository verification outside the team. Include concrete "
                "quality gates and retry/back-edge behavior."
            ),
            "bind.md": (
                "Include all mandatory Resource Constraints, Behavioral Constraints "
                "and Failure Handling sections. Define concrete numeric wall-clock, "
                "token and teammate timeout limits; bounded retry/shutdown; degraded "
                "mode; and explicit treatment of completed work when Team stream "
                "shutdown itself times out."
            ),
        }.get(
            path,
            (
                f"Generate the final role file for role id {role_id}. "
                "Identity MUST start with a first-person motto. Include all five "
                "required sections. Boundary MUST include Forbidden and Mandatory. "
                "Inline Persona MUST be self-contained and preserve strict role "
                "separation. Do not invent dependencies."
            ),
        )

        prompt = f"""
Generate exactly ONE final file for a sandbox JiuwenSwarm Swarm Skill candidate.

Do not explain your reasoning. Do not restate the authoring stages.
Immediately call emit_swarm_skill_file with path={path!r} and final content.

{self._common_constraints(proposal, name)}

FILE-SPECIFIC RULES:
{file_rules}

AUTHORITATIVE JIUWENSWARM TEMPLATE FOR THIS FILE:
{template}

Delete all template notes, comments, placeholders and angle-bracket examples.
Return only via emit_swarm_skill_file.
""".strip()

        tool = {
            "type": "function",
            "function": {
                "name": "emit_swarm_skill_file",
                "description": "Submit one final Swarm Skill file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "enum": [path]},
                        "content": {"type": "string", "minLength": 1},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
        }

        try:
            async with asyncio.timeout(timeout):
                response = await model.invoke(
                    messages=[{"role": "user", "content": prompt}],
                    tools=[tool],
                    tool_choice={
                        "type": "function",
                        "function": {"name": "emit_swarm_skill_file"},
                    },
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Swarm Skill creator timed out generating {path} "
                f"with model {model_name} after {timeout}s"
            ) from exc

        calls = [
            call for call in (response.tool_calls or [])
            if getattr(call, "name", "") == "emit_swarm_skill_file"
        ]
        if len(calls) != 1:
            raise RuntimeError(
                f"creator model failed structured file generation for {path}: "
                f"finish_reason={getattr(response, 'finish_reason', None)!r}, "
                f"tool_calls={len(response.tool_calls or [])}, "
                f"content_length={len(getattr(response, 'content', '') or '')}"
            )

        try:
            arguments = json.loads(calls[0].arguments)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"creator returned invalid JSON tool arguments for {path}"
            ) from exc

        emitted_path = str(arguments.get("path", "")).strip()
        emitted_content = arguments.get("content")
        if emitted_path != path:
            raise RuntimeError(
                f"creator emitted unexpected path {emitted_path!r}; expected {path!r}"
            )
        if not isinstance(emitted_content, str) or not emitted_content.strip():
            raise RuntimeError(f"creator emitted empty content for {path}")

        return {"path": path, "content": emitted_content.strip() + "\n"}

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
            raise ValueError(
                "creation proposal unexpectedly indicates production write"
            )

        validator_path = self._creator_root / "scripts" / "validate_swarmskill.py"
        if not validator_path.is_file():
            raise FileNotFoundError(
                f"JiuwenSwarm validator missing: {validator_path}"
            )

        # Load official templates before making any model call. Missing external
        # creator assets therefore fail deterministically and cheaply.
        templates = {
            "SKILL.md": self._template(_TEMPLATE_BY_FILE["SKILL.md"]),
            "workflow.md": self._template(_TEMPLATE_BY_FILE["workflow.md"]),
            "bind.md": self._template(_TEMPLATE_BY_FILE["bind.md"]),
            **{
                f"roles/{role_id}.md": self._template("role.md.template")
                for role_id in _ROLE_IDS
            },
        }

        name = _candidate_name(proposal)
        model, model_name = self._build_model()

        # Cross-file dependency content is deterministic for this first
        # candidate. The remaining six authored files are small independent
        # structured calls, eliminating the previous 12k-token monolithic call.
        paths = [
            "SKILL.md",
            "roles/leader.md",
            "roles/coding.md",
            "roles/review.md",
            "workflow.md",
            "bind.md",
        ]
        files: list[dict[str, str]] = []
        for file_path in paths:
            files.append(
                await self._generate_file(
                    model=model,
                    model_name=model_name,
                    proposal=proposal,
                    name=name,
                    path=file_path,
                    template=templates[file_path],
                )
            )
        files.append({
            "path": "dependencies.yaml",
            "content": self._dependencies_content(),
        })

        _validate_bundle_shape(name, files)
        payload = {
            "format": _FORMAT,
            "name": name,
            "files": sorted(files, key=lambda item: item["path"]),
        }
        artifact_content = json.dumps(
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
                content=artifact_content,
                metadata={"candidate_format": _FORMAT},
            ),
            base_artifact_id=f"team-pattern-proposal:{proposal.proposal_id}",
            base_version="proposal-v1",
            provider_id=self.provider_id,
            change_summary=(
                "Generated a staged sandbox Swarm Skill candidate from an "
                "explicitly approved repeated AgentTeam collaboration proposal."
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
                content=artifact_content,
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
                "creator_strategy": "staged-per-file-v2",
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
                    "JiuwenSwarm official validator rejected staged candidate:\n"
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
