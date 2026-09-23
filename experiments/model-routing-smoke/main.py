"""Credential-free smoke for TaskProfile -> MoMA routing."""

from __future__ import annotations

import asyncio

from devopspilot.adapters.moma import MoMAProvider, MoMARoute
from devopspilot.contracts.model_intelligence import (
    ModelCapability,
    RiskLevel,
    TaskProfile,
    TaskType,
)
from devopspilot.routing import DefaultCapabilityPolicy, ModelRouter


async def main() -> None:
    provider = MoMAProvider(
        connection_ref="env://MOMA_API_KEY",
        bootstrap_model="bootstrap-model",
        routes={
            ModelCapability.FAST: MoMARoute("fast-model"),
            ModelCapability.REASONING: MoMARoute("reasoning-model"),
            ModelCapability.CODING: MoMARoute("coding-model"),
            ModelCapability.REVIEW: MoMARoute("review-model"),
            ModelCapability.JUDGE: MoMARoute("judge-model"),
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
    assert coding.model_id == "coding-model"

    review = await router.route(TaskProfile(
        task_id="review-1",
        task_type=TaskType.CODE_REVIEW,
        complexity=3,
        risk_level=RiskLevel.HIGH,
        review_requirement=5,
    ))
    assert review.capability is ModelCapability.REVIEW
    assert review.model_id == "review-model"

    issue = await router.route(TaskProfile(
        task_id="issue-1",
        task_type=TaskType.ISSUE_ANALYSIS,
        complexity=1,
        risk_level=RiskLevel.LOW,
    ))
    assert issue.capability is ModelCapability.FAST
    assert issue.model_id == "fast-model"

    high_risk = await router.route(TaskProfile(
        task_id="risk-1",
        task_type=TaskType.ISSUE_ANALYSIS,
        complexity=2,
        risk_level=RiskLevel.CRITICAL,
    ))
    assert high_risk.capability is ModelCapability.REASONING

    fallback = MoMAProvider(
        connection_ref="env://MOMA_API_KEY",
        bootstrap_model="bootstrap-model",
    )
    fallback_decision = await fallback.resolve(
        TaskProfile(
            task_id="fallback-1",
            task_type=TaskType.CODING,
            complexity=2,
            risk_level=RiskLevel.LOW,
        ),
        ModelCapability.CODING,
    )
    assert fallback_decision.model_id == "bootstrap-model"
    assert fallback_decision.metadata["bootstrap_fallback"] is True

    health = await provider.health()
    assert health["credentials_exposed"] is False

    print("MODEL_CAPABILITY_POLICY_OK")
    print("MOMA_DIRECT_ROUTING_OK")
    print("MOMA_BOOTSTRAP_FALLBACK_OK")
    print("MOMA_SECRET_BOUNDARY_OK")


if __name__ == "__main__":
    asyncio.run(main())
