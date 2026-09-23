"""Provider-neutral task profiling and model-routing contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class TaskType(StrEnum):
    ISSUE_ANALYSIS = "issue-analysis"
    CODING = "coding"
    CODE_REVIEW = "code-review"
    TEST_GENERATION = "test-generation"
    CI_DEBUG = "ci-debug"
    DEPENDENCY_DEBUG = "dependency-debug"
    RELEASE_RISK = "release-risk"
    INCIDENT_RCA = "incident-rca"
    RESEARCH = "research"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ModelCapability(StrEnum):
    FAST = "fast"
    REASONING = "reasoning"
    CODING = "coding"
    REVIEW = "review"
    JUDGE = "judge"


class ModelRuntimeFeature(StrEnum):
    BASIC_CHAT = "basic-chat"
    STRUCTURED_TOOL_CALLING = "structured-tool-calling"
    STREAMING = "streaming"
    STRUCTURED_OUTPUT = "structured-output"
    VISION = "vision"


class RouteMode(StrEnum):
    """How a MaaS provider resolves the concrete model."""

    DIRECT = "direct"
    MANAGED = "managed"


@dataclass(frozen=True, slots=True)
class TaskProfile:
    """A description of the engineering task, not of a concrete model."""

    task_id: str
    task_type: TaskType
    complexity: int
    risk_level: RiskLevel
    context_size: int = 0
    reasoning_requirement: int = 0
    coding_requirement: int = 0
    review_requirement: int = 0
    latency_budget_ms: int | None = None
    cost_budget: float | None = None
    privacy_level: str = "standard"
    industry: str | None = None
    project: str | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        for name in (
            "complexity",
            "reasoning_requirement",
            "coding_requirement",
            "review_requirement",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 5:
                raise ValueError(f"{name} must be between 0 and 5")
        if self.context_size < 0:
            raise ValueError("context_size must be >= 0")
        if self.latency_budget_ms is not None and self.latency_budget_ms <= 0:
            raise ValueError("latency_budget_ms must be > 0")
        if self.cost_budget is not None and self.cost_budget < 0:
            raise ValueError("cost_budget must be >= 0")


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """A portable routing result.

    connection_ref points to runtime configuration/secret storage. It is not
    an API key and must never contain credentials.

    verified_features contains only capabilities backed by live/provider
    evidence. Tool-using AgentTeam roles must not infer features from model
    names.
    """

    provider_id: str
    connection_ref: str
    capability: ModelCapability
    mode: RouteMode
    model_id: str
    reason: str
    fallback_model_ids: tuple[str, ...] = ()
    verified_features: frozenset[ModelRuntimeFeature] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("provider_id", "connection_ref", "model_id", "reason"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
