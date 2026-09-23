"""Translate canonical trajectories into DevOpsBench runtime metrics."""

from __future__ import annotations

from typing import Any

from devopspilot.contracts.trajectory import (
    DeliveryTrajectory,
    TrajectoryEventKind,
)


def trajectory_runtime_metrics(
    trajectory: DeliveryTrajectory,
    *,
    duration_ms: int | None = None,
    estimated_cost: float | None = None,
    artifacts: tuple[str, ...] = (),
    runtime_clean_completion: bool | None = None,
) -> dict[str, Any]:
    if duration_ms is not None and duration_ms < 0:
        raise ValueError("duration_ms must be >= 0")
    if estimated_cost is not None and estimated_cost < 0:
        raise ValueError("estimated_cost must be >= 0")

    human_interventions = sum(
        event.kind is TrajectoryEventKind.HUMAN
        for event in trajectory.events
    )
    result: dict[str, Any] = {
        "model_calls": trajectory.model_calls,
        "tool_calls": trajectory.tool_calls,
        "input_tokens": trajectory.input_tokens,
        "output_tokens": trajectory.output_tokens,
        "estimated_cost": estimated_cost,
        "human_interventions": human_interventions,
        "artifacts": list(artifacts),
        "runtime_clean_completion": runtime_clean_completion,
    }
    if duration_ms is not None:
        result["duration_ms"] = duration_ms
    return result
