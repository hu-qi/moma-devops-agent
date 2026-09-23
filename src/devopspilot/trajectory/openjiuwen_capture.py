"""Lifecycle wrapper for OpenJiuwen's shared trajectory processor."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devopspilot.contracts.trajectory import DeliveryTrajectory
from .openjiuwen_bridge import openjiuwen_to_delivery_trajectory


DEFAULT_OPENJIUWEN_SPAN_CATEGORIES = frozenset({
    "llm",
    "tool",
    "agent",
    "task",
    "member",
    "message",
    "event",
})


@dataclass(frozen=True, slots=True)
class OpenJiuwenCaptureResult:
    trajectory: DeliveryTrajectory | None
    issues: tuple[dict[str, Any], ...]


class OpenJiuwenTrajectoryCapture:
    """Capture one invoke-local OpenJiuwen execution.

    Team root spans are intentionally omitted in V1 because OpenJiuwen requires
    an explicit trace_id for the team category. Model/tool/member/task spans
    are sufficient for DevOpsBench runtime metrics and first-stage RSI mining.
    """

    def __init__(
        self,
        *,
        task_id: str,
        repository: str,
        categories: frozenset[str] = DEFAULT_OPENJIUWEN_SPAN_CATEGORIES,
        exporter: str = "file",
        traces_dir: str | Path | None = None,
    ) -> None:
        self.task_id = task_id
        self.repository = repository
        self.categories = categories
        self.exporter = exporter
        self.traces_dir = str(traces_dir) if traces_dir is not None else None
        self._processor: Any | None = None
        self._subscription: Any | None = None
        self._release: Any | None = None
        self._started = False

    def start(self) -> None:
        if self._started:
            raise RuntimeError("OpenJiuwenTrajectoryCapture already started")

        from openjiuwen.agent_teams.observability import (
            ObservabilityConfig,
            acquire_observability,
            release_observability,
        )
        from openjiuwen.extensions.observability.demand import (
            get_trajectory_span_processor,
        )

        config_kwargs: dict[str, Any] = {"exporter": self.exporter}
        if self.exporter == "file" and self.traces_dir:
            config_kwargs["traces_dir"] = self.traces_dir
        acquire_observability(ObservabilityConfig(**config_kwargs))
        processor = get_trajectory_span_processor()
        subscription = processor.subscribe(
            include_span_categories=self.categories,
        )

        self._processor = processor
        self._subscription = subscription
        self._release = release_observability
        self._started = True

    def drain(self) -> OpenJiuwenCaptureResult:
        if not self._started or self._processor is None:
            raise RuntimeError("OpenJiuwenTrajectoryCapture is not started")

        trajectory, raw_issues = self._processor.drain(self._subscription)
        issues = tuple(dict(issue) for issue in raw_issues)
        converted = None
        if trajectory is not None:
            converted = openjiuwen_to_delivery_trajectory(
                trajectory,
                task_id=self.task_id,
                repository=self.repository,
            )
        return OpenJiuwenCaptureResult(
            trajectory=converted,
            issues=issues,
        )

    def close(self) -> None:
        """Release capture after Runner.stop() drained detached callbacks."""

        if not self._started:
            return
        try:
            if self._processor is not None and self._subscription is not None:
                self._processor.unsubscribe(self._subscription)
        finally:
            if self._release is not None:
                self._release()
            self._processor = None
            self._subscription = None
            self._release = None
            self._started = False
