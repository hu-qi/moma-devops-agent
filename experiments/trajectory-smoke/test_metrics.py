"""Smoke for trajectory -> DevOpsBench runtime metrics."""

from __future__ import annotations

from devopspilot.contracts.trajectory import (
    DeliveryTrajectory,
    TrajectoryEvent,
    TrajectoryEventKind,
)
from devopspilot.evaluation import trajectory_runtime_metrics


def main() -> None:
    trajectory = DeliveryTrajectory(
        trajectory_id="traj-1",
        task_id="task-1",
        repository="acme/demo",
        events=(
            TrajectoryEvent(
                1,
                TrajectoryEventKind.ROUTING,
                "model.invoke",
                "success",
                {"input_tokens": 100, "output_tokens": 20},
            ),
            TrajectoryEvent(
                2,
                TrajectoryEventKind.TOOL,
                "shell.execute",
                "success",
            ),
            TrajectoryEvent(
                3,
                TrajectoryEventKind.ROUTING,
                "model.invoke",
                "success",
                {"input_tokens": 200, "output_tokens": 50},
            ),
            TrajectoryEvent(
                4,
                TrajectoryEventKind.HUMAN,
                "approval",
                "approved",
            ),
        ),
    )

    metrics = trajectory_runtime_metrics(
        trajectory,
        duration_ms=2500,
        estimated_cost=0.12,
        artifacts=("trajectory.json",),
    )
    assert metrics == {
        "duration_ms": 2500,
        "model_calls": 2,
        "tool_calls": 1,
        "input_tokens": 300,
        "output_tokens": 70,
        "estimated_cost": 0.12,
        "human_interventions": 1,
        "artifacts": ["trajectory.json"],
        "runtime_clean_completion": None,
    }

    print("TRAJECTORY_DEVOPSBENCH_METRICS_OK")


if __name__ == "__main__":
    main()
