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
        "Orchestrates bounded tasks, dependencies, completion signals, timeouts, "
        "and the final external-verification handoff."
    ),
    "coding": (
        "Implements the assigned software change and reports completion with "
        "repository evidence."
    ),
    "review": (
        "Independently judges the Coding output and returns an explicit approve "
        "or request-changes verdict."
    ),
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
    return f"devopspilot-{value}-swarm"[:80].rstrip("-")


def _validate_bundle_shape(name: str, files: list[dict[str, Any]]) -> None:
    if not files:
        raise ValueError("Swarm Skill candidate contains no files")

    seen: set[str] = set()
    roles: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("candidate file entries must be objects")
        raw_path = str(item.get("path", "")).strip()
        item_content = item.get("content")
        if not raw_path or not isinstance(item_content, str) or not item_content.strip():
            raise ValueError("candidate file requires non-empty path/content")

        item_path = PurePosixPath(raw_path)
        if item_path.is_absolute() or ".." in item_path.parts:
            raise ValueError(f"unsafe candidate path: {raw_path}")
        normalized = item_path.as_posix()
        if normalized in seen:
            raise ValueError(f"duplicate candidate path: {normalized}")
        seen.add(normalized)

        if normalized.startswith("roles/") and normalized.endswith(".md"):
            if len(item_path.parts) != 2:
                raise ValueError(f"nested role path is unsupported: {normalized}")
            roles.add(normalized)
        elif normalized not in _REQUIRED_FILES:
            raise ValueError(f"unexpected Swarm Skill file: {normalized}")

    missing = _REQUIRED_FILES - seen
    if missing:
        raise ValueError(
            "Swarm Skill candidate missing required files: "
            + ", ".join(sorted(missing))
        )

    expected_roles = {f"roles/{role_id}.md" for role_id in _ROLE_IDS}
    if roles != expected_roles:
        raise ValueError(
            f"expected role files {sorted(expected_roles)}, got {sorted(roles)}"
        )

    skill_md = next(item["content"] for item in files if item["path"] == "SKILL.md")
    if f"name: {name}" not in skill_md and f'name: "{name}"' not in skill_md:
        raise ValueError(f"SKILL.md name must be {name!r}")


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

    Long Markdown bodies are generated as normal assistant content, not tool-call
    arguments. Live evidence showed that models which reliably call tools for
    small structured parameters can still truncate, emit placeholders, or time
    out when a tool argument contains several thousand Markdown tokens.

    Candidate identity, paths, SKILL metadata and dependencies are deterministic.
    LLM generation is limited to role, workflow and bind content, followed by
    JiuwenSwarm official validation. Production skills are never written.
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

    def _template_core(self, filename: str) -> str:
        template_path = self._creator_root / "templates" / filename
        if not template_path.is_file():
            raise FileNotFoundError(
                f"JiuwenSwarm creator template missing: {template_path}"
            )
        template = template_path.read_text(encoding="utf-8")
        return template.split("<!--", 1)[0].rstrip()

    @staticmethod
    def _dependencies_content() -> str:
        return (
            "# DevOpsPilot sandbox candidate dependency manifest\n"
            "# The first Team Pattern A/B intentionally adds no external dependency.\n"
            "skills: []\n"
            "tools: []\n"
        )

    @staticmethod
    def _skill_content(name: str) -> str:
        leader = _ROLE_PURPOSES["leader"]
        coding = _ROLE_PURPOSES["coding"]
        review = _ROLE_PURPOSES["review"]
        return f"""---
name: {name}
description: |
  Three-role DevOps delivery pipeline that separates orchestration, implementation, and independent review with bounded completion handling.
  Use when a software-delivery task needs Coding and Review isolation plus deterministic Leader finalization.
  Do NOT use for single-agent edits or as a substitute for external repository verification.
version: "0.1"
kind: swarm-skill
roles:
  - id: leader
    kind: ai_agent
    purpose: {leader}
    skills: []
    tools: []
  - id: coding
    kind: ai_agent
    purpose: {coding}
    skills: []
    tools: []
  - id: review
    kind: ai_agent
    purpose: {review}
    skills: []
    tools: []
---

# DevOpsPilot Bounded Delivery Swarm

A specialization pipeline for the repeated failure mode where useful Coding and
Review work completes but team finalization or shutdown remains open. Independent
repository verification remains outside the team.

## Workflow

0. **Pre-flight: check dependencies** — read [dependencies.yaml](dependencies.yaml),
   report missing items, and let the user decide go/no-go.
1. **Plan** — Leader defines the bounded Coding task, acceptance criteria, and handoff.
2. **Implement** — Coding makes only the assigned change and returns repository evidence.
3. **Review** — Review independently evaluates the Coding output and emits a verdict.
4. **Finalize** — Leader records member completion, timeout/degraded state, and hands
   the candidate to external repository verification. See [workflow.md](workflow.md)
   and [bind.md](bind.md) for the full protocol and limits.

## Roles

| id | Purpose | When dispatched | Input | Key dependencies | Role file |
|---|---|---|---|---|---|
| leader | Orchestrate and finalize | Every run | Delivery task and member outputs | none | [roles/leader.md](roles/leader.md) |
| coding | Implement bounded change | After Leader plan | Task and acceptance criteria | none | [roles/coding.md](roles/coding.md) |
| review | Independently judge change | After Coding completion | Diff and test evidence | none | [roles/review.md](roles/review.md) |

> Before dispatching each teammate, read its role file and paste the Inline Persona
> section into the dispatch prompt.

## Files

| File | What it contains | When to read |
|---|---|---|
| [workflow.md](workflow.md) | Mermaid topology, protocol, gates, final report | Before dispatch |
| [bind.md](bind.md) | Limits, shutdown rules, failure/degraded handling | Before execution and on failure |
| [roles/*.md](roles/) | Role identity, boundary, schema, inline persona | Before each role dispatch |
| [dependencies.yaml](dependencies.yaml) | Startup dependencies | Pre-flight |
"""

    @staticmethod
    def _common_constraints(
        proposal: TeamPatternCreationProposal,
        name: str,
    ) -> str:
        evidence = "\n".join(f"- {item}" for item in proposal.evidence)
        return f"""Candidate name: {name}
Pattern: C-pattern specialization pipeline with an isolated Review gate.

Approved reusable guidance:
{proposal.reusable_guidance}

Evidence:
{evidence}

Fixed roles:
- leader: {_ROLE_PURPOSES["leader"]}
- coding: {_ROLE_PURPOSES["coding"]}
- review: {_ROLE_PURPOSES["review"]}

Mandatory invariants:
- Coding implements; Review judges independently; Leader orchestrates/finalizes.
- Review MUST NOT implement fixes and Coding MUST NOT self-approve.
- External repository verification remains outside the team.
- Leader MUST NOT declare delivery complete before external verification.
- Explicit task dependencies and deterministic completion are required.
- Timeout/shutdown handling MUST preserve already-completed member evidence.
- Include a bounded degraded mode; do not hide runtime degradation.
- No external role dependencies in this first sandbox candidate.
- No executable workflow script in this V1 candidate.
- Never claim production promotion.
""".strip()

    @staticmethod
    def _strip_outer_fence(value: str) -> str:
        content = value.strip()
        lines = content.splitlines()
        if (
            len(lines) >= 2
            and lines[0].strip().startswith("~~~")
            and lines[-1].strip() == "~~~"
        ):
            return "\n".join(lines[1:-1]).strip()
        return content

    async def _generate_markdown(
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
        max_tokens = int(os.getenv("DEVOPSPILOT_SWARM_FILE_MAX_TOKENS", "4000"))
        role_id = PurePosixPath(path).stem if path.startswith("roles/") else ""

        if path == "workflow.md":
            rules = (
                "Include Overview with a valid Mermaid C-pattern pipeline, Detailed "
                "Steps with concrete quality gates, and Acceptance Criteria. Show "
                "Leader -> Coding -> Review -> Leader finalization -> external "
                "verification. Include timeout/degraded back-edges linked to bind.md."
            )
        elif path == "bind.md":
            rules = (
                "Include Resource Constraints, Behavioral Constraints, and Failure "
                "Handling. Use concrete numeric teammate timeout, wall-clock and "
                "token budgets; bounded retry/shutdown; preserve completed evidence "
                "on stream-finalization timeout; define degraded mode and escalation "
                "without weakening external verification."
            )
        else:
            rules = (
                f"Write role {role_id}. Include exactly the five required sections: "
                "Identity, Success Criteria, Boundary, Output Schema, Inline Persona "
                "for Teammate. Identity first line must be a first-person motto in "
                "blockquote italics. Boundary must contain Forbidden and Mandatory. "
                "Output Schema and Inline Persona output format must agree. Keep the "
                "role stage-distinct and do not invent dependencies."
            )

        prompt = f"""Write exactly ONE final JiuwenSwarm Swarm Skill file: {path}.

Return the raw file content only. Do not wrap the whole response in a code fence.
Do not explain your reasoning. Delete all placeholders and template notes.

{self._common_constraints(proposal, name)}

FILE RULES:
{rules}

AUTHORITATIVE FILE TEMPLATE SKELETON:
{template}
""".strip()

        print(f"SWARM_CREATOR_FILE_START={path} model={model_name}")
        try:
            async with asyncio.timeout(timeout):
                response = await model.invoke(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
        except TimeoutError as exc:
            raise RuntimeError(
                f"Swarm Skill creator timed out generating {path} "
                f"with model {model_name} after {timeout}s"
            ) from exc

        finish_reason = getattr(response, "finish_reason", None)
        raw_content = getattr(response, "content", None)
        if not isinstance(raw_content, str) or not raw_content.strip():
            raise RuntimeError(
                f"creator returned no file content for {path}: "
                f"finish_reason={finish_reason!r}"
            )
        if finish_reason == "length":
            raise RuntimeError(
                f"creator hit token limit generating {path}; "
                f"content_length={len(raw_content)}"
            )

        generated = self._strip_outer_fence(raw_content)
        if (
            "<role-id" in generated
            or "<Step name>" in generated
            or "TEMPLATE NOTES" in generated
        ):
            raise RuntimeError(f"creator left template placeholders in {path}")

        print(
            f"SWARM_CREATOR_FILE_COMPLETE={path} "
            f"chars={len(generated)} finish_reason={finish_reason}"
        )
        return {"path": path, "content": generated.rstrip() + "\n"}

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
            raise ValueError("proposal unexpectedly indicates production write")

        validator_path = self._creator_root / "scripts" / "validate_swarmskill.py"
        if not validator_path.is_file():
            raise FileNotFoundError(f"JiuwenSwarm validator missing: {validator_path}")

        templates = {
            f"roles/{role_id}.md": self._template_core("role.md.template")
            for role_id in _ROLE_IDS
        }
        templates["workflow.md"] = self._template_core("workflow.md.template")
        templates["bind.md"] = self._template_core("bind.md.template")

        name = _candidate_name(proposal)
        model, model_name = self._build_model()

        files: list[dict[str, str]] = [
            {"path": "SKILL.md", "content": self._skill_content(name)}
        ]
        for file_path in (
            "roles/leader.md",
            "roles/coding.md",
            "roles/review.md",
            "workflow.md",
            "bind.md",
        ):
            files.append(
                await self._generate_markdown(
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
                "creator_strategy": "plain-content-per-file-v3",
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

        print("JIUWENSWARM_OFFICIAL_VALIDATOR=passed")
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
