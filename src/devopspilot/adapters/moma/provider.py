"""MoMA control-plane routing adapter.

Model invocation is performed by OpenJiuwen. This provider only resolves a
portable RoutingDecision and never exposes credentials.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from devopspilot.contracts.model_intelligence import (
    ModelCapability,
    RouteMode,
    RoutingDecision,
    TaskProfile,
)


@dataclass(frozen=True, slots=True)
class MoMARoute:
    model_id: str
    mode: RouteMode = RouteMode.DIRECT
    fallback_model_ids: tuple[str, ...] = ()
    metadata: Mapping[str, Any] | None = None


class MoMAProvider:
    provider_id = "moma"

    def __init__(
        self,
        *,
        connection_ref: str,
        bootstrap_model: str,
        routes: Mapping[ModelCapability, MoMARoute] | None = None,
        api_base: str | None = None,
    ) -> None:
        if not connection_ref.strip():
            raise ValueError("connection_ref must not be empty")
        if not bootstrap_model.strip():
            raise ValueError("bootstrap_model must not be empty")
        self._connection_ref = connection_ref
        self._bootstrap_model = bootstrap_model
        self._routes = dict(routes or {})
        self._api_base = api_base

    @classmethod
    def from_env(cls) -> "MoMAProvider":
        bootstrap = os.getenv("MOMA_MODEL", "").strip()
        if not bootstrap:
            raise RuntimeError("Missing required environment variable: MOMA_MODEL")

        env_by_capability = {
            ModelCapability.FAST: "MOMA_FAST_MODEL",
            ModelCapability.REASONING: "MOMA_REASONING_MODEL",
            ModelCapability.CODING: "MOMA_CODING_MODEL",
            ModelCapability.REVIEW: "MOMA_REVIEW_MODEL",
            ModelCapability.JUDGE: "MOMA_JUDGE_MODEL",
        }
        routes: dict[ModelCapability, MoMARoute] = {}
        for capability, env_name in env_by_capability.items():
            model = os.getenv(env_name, "").strip()
            if model:
                routes[capability] = MoMARoute(model_id=model)

        return cls(
            connection_ref=os.getenv(
                "MOMA_CONNECTION_REF", "env://MOMA_API_KEY"
            ),
            bootstrap_model=bootstrap,
            routes=routes,
            api_base=os.getenv("MOMA_API_BASE", "").strip() or None,
        )

    async def resolve(
        self,
        task: TaskProfile,
        capability: ModelCapability,
    ) -> RoutingDecision:
        route = self._routes.get(capability)
        if route is None:
            route = MoMARoute(
                model_id=self._bootstrap_model,
                metadata={"bootstrap_fallback": True},
            )
            reason = (
                f"No explicit {capability.value} route is configured; "
                "using the MoMA bootstrap/default model."
            )
        else:
            reason = (
                f"Task {task.task_id} requires {capability.value}; "
                "using the configured MoMA capability route."
            )

        metadata = dict(route.metadata or {})
        metadata.update({
            "task_type": task.task_type.value,
            "risk_level": task.risk_level.value,
            "complexity": task.complexity,
        })
        return RoutingDecision(
            provider_id=self.provider_id,
            connection_ref=self._connection_ref,
            capability=capability,
            mode=route.mode,
            model_id=route.model_id,
            fallback_model_ids=route.fallback_model_ids,
            reason=reason,
            metadata=metadata,
        )

    async def health(self) -> Mapping[str, Any]:
        return {
            "provider_id": self.provider_id,
            "configured": bool(self._bootstrap_model and self._connection_ref),
            "api_base_configured": bool(self._api_base),
            "bootstrap_model": self._bootstrap_model,
            "explicit_routes": {
                capability.value: route.model_id
                for capability, route in self._routes.items()
            },
            "credentials_exposed": False,
        }
