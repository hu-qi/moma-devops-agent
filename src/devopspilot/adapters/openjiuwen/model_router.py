"""Translate DevOpsPilot role routing into OpenJiuwen AgentTeam model-router config."""

from __future__ import annotations

from dataclasses import dataclass

from devopspilot.routing.roles import AgentTeamModelPlan


@dataclass(frozen=True, slots=True)
class OpenJiuwenTeamModelRouting:
    model_router: dict
    leader_model: str
    coding_model: str
    review_model: str


def build_team_model_routing(
    plan: AgentTeamModelPlan,
    *,
    api_base: str,
    api_key: str,
    timeout: float = 120.0,
) -> OpenJiuwenTeamModelRouting:
    if not api_base.strip():
        raise ValueError("api_base must not be empty")
    if not api_key.strip():
        raise ValueError("api_key must not be empty")

    ordered = [
        plan.leader.model_id,
        plan.coding.model_id,
        plan.review.model_id,
    ]
    model_names: list[str] = []
    for model in ordered:
        if model not in model_names:
            model_names.append(model)

    return OpenJiuwenTeamModelRouting(
        model_router={
            "api_base_url": api_base,
            "api_key": api_key,
            "api_provider": "OpenAI",
            "model_names": model_names,
            "metadata": {
                "client": {
                    "endpoint_profile": "openai_compatible",
                    "timeout": timeout,
                },
                "request": {
                    "temperature": 0,
                },
            },
        },
        leader_model=plan.leader.model_id,
        coding_model=plan.coding.model_id,
        review_model=plan.review.model_id,
    )
