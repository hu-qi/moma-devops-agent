"""Role-level model planning for DevOpsPilot AgentTeam."""

from __future__ import annotations

from dataclasses import dataclass, replace

from devopspilot.contracts.model_intelligence import (
    ModelCapability,
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
    """Resolve independent model decisions for core delivery-team roles."""

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
        return AgentTeamModelPlan(
            leader=leader,
            coding=coding,
            review=review,
        )
