"""Live-verified MoMA model capability evidence.

This is intentionally a small evidence registry, not a marketing model catalog.
A model is added only after DevOpsPilot has exercised the relevant capability
through the configured MoMA OpenAI-compatible endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass

from devopspilot.contracts.model_intelligence import ModelRuntimeFeature


@dataclass(frozen=True, slots=True)
class MoMAModelEvidence:
    model_id: str
    verified_features: frozenset[ModelRuntimeFeature]
    eligible_for_tool_agent: bool
    evidence: str
    notes: str = ""


_TOOL_AGENT = frozenset({
    ModelRuntimeFeature.BASIC_CHAT,
    ModelRuntimeFeature.STRUCTURED_TOOL_CALLING,
})


MODEL_EVIDENCE: dict[str, MoMAModelEvidence] = {
    "GLM-5.3": MoMAModelEvidence(
        model_id="GLM-5.3",
        verified_features=_TOOL_AGENT,
        eligible_for_tool_agent=True,
        evidence="MoMA Role Model Matrix / live CI",
    ),
    "Qwen3-32B": MoMAModelEvidence(
        model_id="Qwen3-32B",
        verified_features=_TOOL_AGENT,
        eligible_for_tool_agent=True,
        evidence="MoMA Role Model Matrix / live CI",
    ),
    "deepseek-v4.1-flash": MoMAModelEvidence(
        model_id="deepseek-v4.1-flash",
        verified_features=_TOOL_AGENT,
        eligible_for_tool_agent=True,
        evidence="MoMA Role Model Matrix / live CI",
    ),
    "deepseek-v4-flash-0731": MoMAModelEvidence(
        model_id="deepseek-v4-flash-0731",
        verified_features=frozenset({
            ModelRuntimeFeature.BASIC_CHAT,
            ModelRuntimeFeature.STRUCTURED_TOOL_CALLING,
            ModelRuntimeFeature.STREAMING,
        }),
        eligible_for_tool_agent=True,
        evidence="MoMA Capability Spikes / live CI",
    ),
    "DeepSeek-R1-0528": MoMAModelEvidence(
        model_id="DeepSeek-R1-0528",
        verified_features=frozenset({ModelRuntimeFeature.BASIC_CHAT}),
        eligible_for_tool_agent=False,
        evidence="MoMA Role Model Matrix / live CI",
        notes=(
            "Basic chat succeeds, but the model emits textual function-call "
            "instructions instead of OpenAI structured tool_calls."
        ),
    ),
    "qwen2.5-coder-32b-Instruct": MoMAModelEvidence(
        model_id="qwen2.5-coder-32b-Instruct",
        verified_features=frozenset({ModelRuntimeFeature.BASIC_CHAT}),
        eligible_for_tool_agent=False,
        evidence="MoMA Role Model Matrix / live CI",
        notes=(
            "Basic chat succeeds, but requested tool use is returned as JSON "
            "text rather than OpenAI structured tool_calls."
        ),
    ),
}


def evidence_for_model(model_id: str) -> MoMAModelEvidence | None:
    return MODEL_EVIDENCE.get(model_id)


def verified_features_for_model(
    model_id: str,
) -> frozenset[ModelRuntimeFeature]:
    evidence = evidence_for_model(model_id)
    return evidence.verified_features if evidence else frozenset()
