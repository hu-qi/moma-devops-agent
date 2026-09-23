"""Smoke for canonical DevOpsPilot trajectory accounting."""

from __future__ import annotations

import asyncio

from devopspilot.contracts.trajectory import TrajectoryEvent, TrajectoryEventKind
from devopspilot.trajectory import InMemoryTrajectoryRecorder


async def main() -> None:
    recorder = InMemoryTrajectoryRecorder(
        trajectory_id="traj-1",
        task_id="task-1",
        repository="acme/demo",
    )
    await recorder.append(TrajectoryEvent(
        sequence=1,
        kind=TrajectoryEventKind.ROUTING,
        name="model.invoke",
        status="success",
        attributes={
            "capability": "coding",
            "model_id": "coding-model",
            "input_tokens": 120,
            "output_tokens": 40,
        },
    ))
    await recorder.append(TrajectoryEvent(
        sequence=2,
        kind=TrajectoryEventKind.TOOL,
        name="shell.execute",
        status="success",
        attributes={"duration_ms": 12},
    ))
    await recorder.append(TrajectoryEvent(
        sequence=3,
        kind=TrajectoryEventKind.CI,
        name="ci.run",
        status="success",
        attributes={"run_id": "100"},
    ))

    trajectory = await recorder.snapshot()
    assert trajectory.model_calls == 1
    assert trajectory.tool_calls == 1
    assert trajectory.input_tokens == 120
    assert trajectory.output_tokens == 40

    try:
        await recorder.append(TrajectoryEvent(
            sequence=3,
            kind=TrajectoryEventKind.HUMAN,
            name="approval",
            status="approved",
        ))
    except ValueError:
        pass
    else:
        raise AssertionError("non-increasing trajectory sequence must be rejected")

    print("TRAJECTORY_SCHEMA_OK")
    print("TRAJECTORY_USAGE_ACCOUNTING_OK")
    print("TRAJECTORY_SEQUENCE_GUARD_OK")


if __name__ == "__main__":
    asyncio.run(main())
