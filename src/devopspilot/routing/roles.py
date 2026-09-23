"""Role-level model planning for DevOpsPilot AgentTeam."""

from __future__ import annotations

from dataclasses import dataclass, replace

from devopspilot.contracts.model_intelligence import (
    ModelCapability,
    ModelRuntimeFeature,
    RoutingDecision,
    TaskProfile,
)
from devopspilot.contracts.providers import MaaSProvider


@dataclass(frozen=True, slots=True)
class AgentTeamModelPlan:
    leader: RoutingDecision
    coding: RoutingDecision
    review: RoutingDecision


class AgentTeamModelPlanner:
    """Resolve and capability-gate models for core delivery-team roles."""

    REQUIRED_TOOL_FEATURES = frozenset({
        ModelRuntimeFeature.STRUCTURED_TOOL_CALLING,
    })

    def __init__(self, provider: MaaSProvider) -> None:
        self._provider = provider

    async def plan(self, task: TaskProfile) -> AgentTeamModelPlan:
        leader_profile = replace(
            task,
            task_id=f"{task.task_id}:leader",
            reasoning_requirement=max(task.reasoning_requirement, 4),
        )
        coding_profile = replace(
            task,
            task_id=f"{task.task_id}:coding",
            coding_requirement=max(task.coding_requirement, 4),
        )
        review_profile = replace(
            task,
            task_id=f"{task.task_id}:review",
            review_requirement=max(task.review_requirement, 4),
        )

        leader = await self._provider.resolve(
            leader_profile,
            ModelCapability.REASONING,
        )
        coding = await self._provider.resolve(
            coding_profile,
            ModelCapability.CODING,
        )
        review = await self._provider.resolve(
            review_profile,
            ModelCapability.REVIEW,
        )

        self._require_tool_role("leader", leader)
        self._require_tool_role("coding", coding)
        self._require_tool_role("review", review)

        return AgentTeamModelPlan(
            leader=leader,
            coding=coding,
            review=review,
        )

    @classmethod
    def _require_tool_role(
        cls,
        role: str,
        decision: RoutingDecision,
    ) -> None:
        missing = cls.REQUIRED_TOOL_FEATURES - decision.verified_features
        if not missing:
            return

        missing_text = ", ".join(sorted(feature.value for feature in missing))
        evidence = decision.metadata.get(
            "model_capability_evidence",
            "unverified",
        )
        raise RuntimeError(
            f"Model {decision.model_id!r} cannot be assigned to AgentTeam "
            f"role {role!r}: missing verified runtime features "
            f"[{missing_text}]; evidence={evidence}. "
            "Run the model capability gate or configure a verified fallback."
        )
