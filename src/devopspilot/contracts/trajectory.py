"""Canonical execution trajectory for evaluation and controlled evolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable


class TrajectoryEventKind(StrEnum):
    ROUTING = "routing"
    AGENT = "agent"
    TOOL = "tool"
    SCM = "scm"
    CI = "ci"
    EVALUATION = "evaluation"
    HUMAN = "human"


@dataclass(frozen=True, slots=True)
class TrajectoryEvent:
    sequence: int
    kind: TrajectoryEventKind
    name: str
    status: str
    attributes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("trajectory event sequence must be >= 0")
        if not self.name.strip():
            raise ValueError("trajectory event name must not be empty")


@dataclass(frozen=True, slots=True)
class DeliveryTrajectory:
    trajectory_id: str
    task_id: str
    repository: str
    events: tuple[TrajectoryEvent, ...]

    @property
    def model_calls(self) -> int:
        return sum(
            event.kind is TrajectoryEventKind.ROUTING
            and event.name == "model.invoke"
            for event in self.events
        )

    @property
    def tool_calls(self) -> int:
        return sum(
            event.kind is TrajectoryEventKind.TOOL
            for event in self.events
        )

    @property
    def input_tokens(self) -> int:
        return sum(
            int(event.attributes.get("input_tokens", 0) or 0)
            for event in self.events
            if event.kind is TrajectoryEventKind.ROUTING
        )

    @property
    def output_tokens(self) -> int:
        return sum(
            int(event.attributes.get("output_tokens", 0) or 0)
            for event in self.events
            if event.kind is TrajectoryEventKind.ROUTING
        )


@runtime_checkable
class TrajectoryRecorder(Protocol):
    async def append(self, event: TrajectoryEvent) -> None:
        ...

    async def snapshot(self) -> DeliveryTrajectory:
        ...
