"""Candidate-only OpenJiuwen Skill Experience evolution provider."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

from devopspilot.contracts.evolution import (
    ArtifactKind,
    ArtifactVersion,
    EvolutionCandidate,
    EvolutionProvider,
    EvolutionRequest,
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def materialize_skill_experience_candidate(
    candidate: EvolutionCandidate,
    *,
    target_skills_root: str | Path,
) -> tuple[str, ...]:
    """Materialize a candidate into an isolated Skill store for evaluation.

    This is separate from production promotion. The caller must provide a
    sandbox copy of the Skill root. OpenJiuwen's own EvolutionStore projection
    logic is used so candidate evaluation sees the same Skill presentation
    that an approved record would create.
    """

    if candidate.artifact.kind is not ArtifactKind.SKILL_EXPERIENCE:
        raise ValueError("candidate is not a Skill Experience artifact")

    payload = json.loads(candidate.artifact.content)
    if payload.get("format") != "devopspilot.skill-experience-candidate/v1":
        raise ValueError("unsupported Skill Experience candidate format")

    skill_name = str(payload.get("skill_name", "")).strip()
    records = payload.get("records")
    if not skill_name or not isinstance(records, list) or not records:
        raise ValueError("candidate must contain one Skill and non-empty records")

    root = Path(target_skills_root).resolve()
    skill_md = root / skill_name / "SKILL.md"
    if not skill_md.is_file():
        raise FileNotFoundError(f"sandbox Skill definition missing: {skill_md}")

    from openjiuwen.agent_evolving.checkpointing.evolution_store import (
        EvolutionStore,
    )
    from openjiuwen.agent_evolving.checkpointing.types import EvolutionRecord

    store = EvolutionStore(str(root))
    record_ids: list[str] = []
    for item in records:
        record = EvolutionRecord.from_dict(item)
        await store.append_record(skill_name, record)
        record_ids.append(record.id)

    return tuple(record_ids)


class OpenJiuwenSkillEvolutionProvider:
    """Generate staged Skill Experience candidates without production writes.

    OpenJiuwen runs against a temporary copy of the Skill store with
    auto_save=False and requires_approval=True. DevOpsPilot reads the staged
    PendingChange payload and converts it to its own EvolutionCandidate. The
    OpenJiuwen approval/persistence path is deliberately never invoked here.
    """

    provider_id = "openjiuwen-skill-evolution"

    def __init__(
        self,
        *,
        skills_root: str | Path,
        model_name: str | None = None,
        language: str = "en",
    ) -> None:
        self._skills_root = Path(skills_root).resolve()
        self._model_name = model_name
        self._language = language

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
        model = Model(
            model_client_config=ModelClientConfig(
                client_provider="OpenAI",
                api_base=_required_env("MOMA_API_BASE"),
                api_key=_required_env("MOMA_API_KEY"),
                endpoint_profile="openai_compatible",
                timeout=180,
            ),
            model_config=ModelRequestConfig(
                model=model_name,
                temperature=0,
            ),
        )
        return model, model_name

    async def generate_candidate(
        self,
        request: EvolutionRequest,
    ) -> EvolutionCandidate:
        if request.base_artifact.kind is not ArtifactKind.SKILL_EXPERIENCE:
            raise ValueError(
                "OpenJiuwenSkillEvolutionProvider only evolves "
                "ArtifactKind.SKILL_EXPERIENCE"
            )
        skill_name = str(
            request.base_artifact.metadata.get("skill_name", "")
        ).strip()
        if not skill_name:
            raise ValueError("base artifact metadata.skill_name is required")
        if not request.signals:
            raise ValueError("at least one attributed evolution signal is required")
        if not (self._skills_root / skill_name / "SKILL.md").is_file():
            raise FileNotFoundError(
                f"Skill definition not found: {self._skills_root / skill_name / 'SKILL.md'}"
            )

        from openjiuwen.agent_evolving.signal.base import make_evolution_signal
        from openjiuwen.agent_evolving.trajectory import TrajectorySpanProcessor
        from openjiuwen.harness.rails import SkillEvolutionRail
        from openjiuwen.harness.rails.evolution import EvolutionReviewRuntime

        model, model_name = self._build_model()
        processor = TrajectorySpanProcessor()

        with tempfile.TemporaryDirectory(
            prefix="devopspilot_skill_evolution_"
        ) as td:
            sandbox_root = Path(td) / "skills"
            shutil.copytree(self._skills_root, sandbox_root)

            rail = SkillEvolutionRail(
                str(sandbox_root),
                llm=model,
                model=model_name,
                signal_trigger=False,
                auto_save=False,
                review_runtime=EvolutionReviewRuntime(),
                language=self._language,
                trajectory_span_processor=processor,
                async_evolution=False,
            )

            signals = []
            for evidence in request.signals:
                context = dict(evidence.metadata)
                if evidence.trajectory_id:
                    context["trajectory_id"] = evidence.trajectory_id
                signals.append(
                    make_evolution_signal(
                        signal_type=evidence.signal_type,
                        section=evidence.section,
                        excerpt=evidence.excerpt,
                        tool_name=evidence.tool_name,
                        skill_name=skill_name,
                        source=evidence.source,
                        context=context,
                    )
                )

            result = await rail.evolve_from_external_signals(
                signals=signals,
                messages=[{
                    "role": "user",
                    "content": request.objective,
                }],
                trajectory=None,
                user_query=request.objective,
                requires_approval=True,
            )

            if result.status != "staged" or result.request is None:
                raise RuntimeError(
                    "OpenJiuwen did not stage an evolution candidate: "
                    f"status={result.status} message={result.message}"
                )
            pending = result.request.pending_change
            if pending is None or not pending.payload:
                raise RuntimeError(
                    "OpenJiuwen staged evolution without pending experience records"
                )

            records = [record.to_dict() for record in pending.payload]
            payload = {
                "format": "devopspilot.skill-experience-candidate/v1",
                "skill_name": skill_name,
                "records": records,
            }
            content = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
            digest = ArtifactVersion(
                artifact_id=request.base_artifact.artifact_id,
                kind=request.base_artifact.kind,
                version="candidate",
                content=content,
            ).digest
            candidate_id = f"{request.request_id}:{digest[:12]}"
            summaries = [
                str(item.get("summary") or item.get("context") or "").strip()
                for item in records
            ]
            summaries = [item for item in summaries if item]

            # Because sandbox_root is destroyed at context exit, no OpenJiuwen
            # staged state can become production state from this provider.
            return EvolutionCandidate(
                candidate_id=candidate_id,
                artifact=ArtifactVersion(
                    artifact_id=request.base_artifact.artifact_id,
                    kind=request.base_artifact.kind,
                    version=(
                        f"{request.base_artifact.version}"
                        f"-candidate.{digest[:8]}"
                    ),
                    content=content,
                    metadata={
                        **dict(request.base_artifact.metadata),
                        "candidate_format": payload["format"],
                    },
                ),
                base_artifact_id=request.base_artifact.artifact_id,
                base_version=request.base_artifact.version,
                provider_id=self.provider_id,
                change_summary=(
                    "; ".join(summaries)[:1200]
                    or f"Staged {len(records)} Skill experience record(s)."
                ),
                source_trajectory_ids=request.source_trajectory_ids,
                metadata={
                    "skill_name": skill_name,
                    "openjiuwen_model": model_name,
                    "openjiuwen_status": result.status,
                    "openjiuwen_pending_request_id": (
                        result.request.request_id or ""
                    ),
                    "record_count": len(records),
                    "sandboxed": True,
                    "production_write": False,
                },
            )
