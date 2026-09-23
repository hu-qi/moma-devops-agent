"""Provider-neutral model router."""

from __future__ import annotations

from typing import Protocol

from devopspilot.contracts.model_intelligence import (
    ModelCapability,
    RoutingDecision,
    TaskProfile,
)
from devopspilot.contracts.providers import MaaSProvider


class CapabilityPolicy(Protocol):
    def select(self, task: TaskProfile) -> ModelCapability:
        ...


class ModelRouter:
    def __init__(
        self,
        *,
        provider: MaaSProvider,
        policy: CapabilityPolicy,
    ) -> None:
        self._provider = provider
        self._policy = policy

    async def route(self, task: TaskProfile) -> RoutingDecision:
        capability = self._policy.select(task)
        return await self._provider.resolve(task, capability)
