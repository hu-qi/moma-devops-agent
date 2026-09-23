"""Derive model-routing TaskProfile from a delivery work item."""

from __future__ import annotations

from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.model_intelligence import (
    RiskLevel,
    TaskProfile,
    TaskType,
)


_TASK_TYPES = {task_type.value: task_type for task_type in TaskType}


_RISK = {
    "low": RiskLevel.LOW,
    "medium": RiskLevel.MEDIUM,
    "high": RiskLevel.HIGH,
    "critical": RiskLevel.CRITICAL,
}


class DeliveryTaskProfiler:
    """Deterministic V1 profiler for software-change tasks.

    Explicit task metadata always wins. Labels are used only as conservative
    hints; no model/vendor information belongs here.
    """

    def profile(self, task: DeliveryTask) -> TaskProfile:
        metadata = task.metadata
        labels = {label.lower() for label in task.work_item.labels}

        risk = _RISK.get(
            metadata.get("risk_level", "").lower(),
            self._risk_from_labels(labels),
        )
        complexity = self._bounded_int(metadata.get("complexity"), default=3)
        context_size = self._nonnegative_int(
            metadata.get("context_size"),
            default=len(task.work_item.title) + len(task.work_item.body),
        )

        task_type = self._task_type(
            metadata.get("task_type"),
            labels,
        )

        return TaskProfile(
            task_id=(
                f"{task.repository.provider_id}:"
                f"{task.repository.repository_id}:"
                f"{task.work_item.item_id}"
            ),
            task_type=task_type,
            complexity=complexity,
            risk_level=risk,
            context_size=context_size,
            reasoning_requirement=self._bounded_int(
                metadata.get("reasoning_requirement"),
                default=4 if risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} else 3,
            ),
            coding_requirement=self._bounded_int(
                metadata.get("coding_requirement"),
                default=5,
            ),
            review_requirement=self._bounded_int(
                metadata.get("review_requirement"),
                default=5 if risk in {RiskLevel.HIGH, RiskLevel.CRITICAL} else 4,
            ),
            latency_budget_ms=self._positive_optional_int(
                metadata.get("latency_budget_ms")
            ),
            cost_budget=self._nonnegative_optional_float(
                metadata.get("cost_budget")
            ),
            privacy_level=metadata.get("privacy_level", "standard"),
            industry=metadata.get("industry"),
            project=task.repository.full_name,
            tags=tuple(sorted(labels)),
            metadata={
                "work_item_title": task.work_item.title,
                "target_branch": task.target_branch,
            },
        )

    @staticmethod
    def _task_type(value: str | None, labels: set[str]) -> TaskType:
        if value:
            normalized = value.strip().lower()
            if normalized not in _TASK_TYPES:
                raise ValueError(f"unsupported task_type: {value}")
            return _TASK_TYPES[normalized]

        if labels & {"ci", "ci-debug", "build", "build-debug"}:
            return TaskType.CI_DEBUG
        if labels & {"review", "code-review"}:
            return TaskType.CODE_REVIEW
        if labels & {"test", "test-generation"}:
            return TaskType.TEST_GENERATION
        if labels & {"dependency", "dependency-debug"}:
            return TaskType.DEPENDENCY_DEBUG
        if labels & {"incident", "rca", "incident-rca"}:
            return TaskType.INCIDENT_RCA
        if labels & {"release", "release-risk"}:
            return TaskType.RELEASE_RISK
        return TaskType.CODING

    @staticmethod
    def _risk_from_labels(labels: set[str]) -> RiskLevel:
        if labels & {"critical", "sev0", "p0", "security-critical"}:
            return RiskLevel.CRITICAL
        if labels & {"high-risk", "sev1", "p1", "security"}:
            return RiskLevel.HIGH
        if labels & {"medium-risk", "sev2", "p2"}:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _bounded_int(value: str | None, *, default: int) -> int:
        if value is None or value == "":
            return default
        parsed = int(value)
        if not 0 <= parsed <= 5:
            raise ValueError("profile score must be between 0 and 5")
        return parsed

    @staticmethod
    def _nonnegative_int(value: str | None, *, default: int) -> int:
        if value is None or value == "":
            return default
        parsed = int(value)
        if parsed < 0:
            raise ValueError("context_size must be >= 0")
        return parsed

    @staticmethod
    def _positive_optional_int(value: str | None) -> int | None:
        if value is None or value == "":
            return None
        parsed = int(value)
        if parsed <= 0:
            raise ValueError("latency_budget_ms must be > 0")
        return parsed

    @staticmethod
    def _nonnegative_optional_float(value: str | None) -> float | None:
        if value is None or value == "":
            return None
        parsed = float(value)
        if parsed < 0:
            raise ValueError("cost_budget must be >= 0")
        return parsed
