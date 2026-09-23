"""Credential-free smoke for TaskProfile -> MoMA routing."""

from __future__ import annotations

import asyncio

from devopspilot.adapters.moma import MoMAProvider, MoMARoute
from devopspilot.adapters.openjiuwen.model_router import build_team_model_routing
from devopspilot.contracts.model_intelligence import (
    ModelCapability,
    ModelRuntimeFeature,
    RiskLevel,
    TaskProfile,
    TaskType,
)
from devopspilot.routing import AgentTeamModelPlanner, DefaultCapabilityPolicy, ModelRouter


async def main() -> None:
    provider = MoMAProvider(
        connection_ref="env://MOMA_API_KEY",
        bootstrap_model="deepseek-v4.1-flash",
        routes={
            ModelCapability.FAST: MoMARoute("deepseek-v4.1-flash"),
            ModelCapability.REASONING: MoMARoute("GLM-5.3"),
            ModelCapability.CODING: MoMARoute("Qwen3-32B"),
            ModelCapability.REVIEW: MoMARoute("deepseek-v4.1-flash"),
            ModelCapability.JUDGE: MoMARoute("GLM-5.3"),
        },
        api_base="https://example.invalid/v1",
    )
    router = ModelRouter(
        provider=provider,
        policy=DefaultCapabilityPolicy(),
    )

    coding = await router.route(TaskProfile(
        task_id="coding-1",
        task_type=TaskType.CODING,
        complexity=3,
        risk_level=RiskLevel.MEDIUM,
        coding_requirement=5,
    ))
    assert coding.capability is ModelCapability.CODING
    assert coding.model_id == "Qwen3-32B"
    assert ModelRuntimeFeature.STRUCTURED_TOOL_CALLING in coding.verified_features

    review = await router.route(TaskProfile(
        task_id="review-1",
        task_type=TaskType.CODE_REVIEW,
        complexity=3,
        risk_level=RiskLevel.HIGH,
        review_requirement=5,
    ))
    assert review.capability is ModelCapability.REVIEW
    assert review.model_id == "deepseek-v4.1-flash"

    issue = await router.route(TaskProfile(
        task_id="issue-1",
        task_type=TaskType.ISSUE_ANALYSIS,
        complexity=1,
        risk_level=RiskLevel.LOW,
    ))
    assert issue.capability is ModelCapability.FAST

    high_risk = await router.route(TaskProfile(
        task_id="risk-1",
        task_type=TaskType.ISSUE_ANALYSIS,
        complexity=2,
        risk_level=RiskLevel.CRITICAL,
    ))
    assert high_risk.capability is ModelCapability.REASONING

    team_plan = await AgentTeamModelPlanner(provider).plan(TaskProfile(
        task_id="delivery-1",
        task_type=TaskType.CODING,
        complexity=4,
        risk_level=RiskLevel.HIGH,
        reasoning_requirement=4,
        coding_requirement=5,
        review_requirement=5,
    ))
    assert team_plan.leader.model_id == "GLM-5.3"
    assert team_plan.coding.model_id == "Qwen3-32B"
    assert team_plan.review.model_id == "deepseek-v4.1-flash"

    runtime_routing = build_team_model_routing(
        team_plan,
        api_base="https://moma.example/v1",
        api_key="runtime-secret-only",
    )
    assert runtime_routing.model_router["model_names"] == [
        "GLM-5.3",
        "Qwen3-32B",
        "deepseek-v4.1-flash",
    ]

    fallback = MoMAProvider(
        connection_ref="env://MOMA_API_KEY",
        bootstrap_model="deepseek-v4.1-flash",
    )
    fallback_plan = await AgentTeamModelPlanner(fallback).plan(TaskProfile(
        task_id="delivery-fallback",
        task_type=TaskType.CODING,
        complexity=2,
        risk_level=RiskLevel.LOW,
    ))
    deduped = build_team_model_routing(
        fallback_plan,
        api_base="https://moma.example/v1",
        api_key="runtime-secret-only",
    )
    assert deduped.model_router["model_names"] == ["deepseek-v4.1-flash"]

    ineligible = MoMAProvider(
        connection_ref="env://MOMA_API_KEY",
        bootstrap_model="DeepSeek-R1-0528",
        routes={
            ModelCapability.REASONING: MoMARoute("DeepSeek-R1-0528"),
            ModelCapability.CODING: MoMARoute("Qwen3-32B"),
            ModelCapability.REVIEW: MoMARoute("deepseek-v4.1-flash"),
        },
    )
    try:
        await AgentTeamModelPlanner(ineligible).plan(TaskProfile(
            task_id="reject-unverified-tool-role",
            task_type=TaskType.CODING,
            complexity=4,
            risk_level=RiskLevel.HIGH,
        ))
    except RuntimeError as exc:
        assert "STRUCTURED" not in str(exc)
        assert "structured-tool-calling" in str(exc)
        assert "DeepSeek-R1-0528" in str(exc)
    else:
        raise AssertionError("tool-ineligible leader model must be rejected")

    health = await provider.health()
    assert health["credentials_exposed"] is False

    print("MODEL_RUNTIME_FEATURE_GATE_OK")
    print("INELIGIBLE_TOOL_MODEL_REJECTED_OK")
    print("OPENJIUWEN_MODEL_ROUTER_MAPPING_OK")
    print("AGENTTEAM_ROLE_ROUTING_OK")
    print("MODEL_CAPABILITY_POLICY_OK")
    print("MOMA_DIRECT_ROUTING_OK")
    print("MOMA_BOOTSTRAP_FALLBACK_OK")
    print("MOMA_SECRET_BOUNDARY_OK")


if __name__ == "__main__":
    asyncio.run(main())
