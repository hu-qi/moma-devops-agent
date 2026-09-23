"""Default TaskProfile -> ModelCapability policy."""

from __future__ import annotations

from devopspilot.contracts.model_intelligence import (
    ModelCapability,
    RiskLevel,
    TaskProfile,
    TaskType,
)


class DefaultCapabilityPolicy:
    """Deterministic V1 capability selection.

    The policy decides the class of intelligence required. It does not know
    model IDs, vendors, endpoints or prices.
    """

    def select(self, task: TaskProfile) -> ModelCapability:
        if task.task_type is TaskType.CODE_REVIEW:
            return ModelCapability.REVIEW

        if task.task_type in {TaskType.CODING, TaskType.TEST_GENERATION}:
            return ModelCapability.CODING

        if task.task_type in {
            TaskType.CI_DEBUG,
            TaskType.DEPENDENCY_DEBUG,
            TaskType.INCIDENT_RCA,
            TaskType.RELEASE_RISK,
            TaskType.RESEARCH,
        }:
            return ModelCapability.REASONING

        if (
            task.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            or task.reasoning_requirement >= 4
            or task.complexity >= 4
        ):
            return ModelCapability.REASONING

        return ModelCapability.FAST
