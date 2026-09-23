"""Smoke for canonical DevOpsPilot trajectory accounting."""

from __future__ import annotations

import asyncio

from devopspilot.contracts.trajectory import TrajectoryEvent, TrajectoryEventKind
from devopspilot.trajectory import (
    DEFAULT_OPENJIUWEN_SPAN_CATEGORIES,
    InMemoryTrajectoryRecorder,
    OpenJiuwenTrajectoryCapture,
)
from devopspilot.trajectory.openjiuwen_bridge import map_openjiuwen_span


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

    capture = OpenJiuwenTrajectoryCapture(
        task_id="task-1",
        repository="acme/demo",
    )
    assert "llm" in capture.categories
    assert "tool" in DEFAULT_OPENJIUWEN_SPAN_CATEGORIES
    assert "team" not in DEFAULT_OPENJIUWEN_SPAN_CATEGORIES

    llm_event = map_openjiuwen_span(
        sequence=4,
        category="llm",
        span_name="chat",
        attributes={
            "gen_ai.response.model": "Qwen3-32B",
            "gen_ai.provider.name": "OpenAI",
            "agentteam.member.name": "coding-agent",
            "openjiuwen.gen_ai.response.total_latency_ms": 1234,
        },
        status={"code": "OK"},
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
        },
    )
    assert llm_event is not None
    assert llm_event.kind is TrajectoryEventKind.ROUTING
    assert llm_event.attributes["model_id"] == "Qwen3-32B"
    assert llm_event.attributes["input_tokens"] == 100

    tool_event = map_openjiuwen_span(
        sequence=5,
        category="tool",
        span_name="tool.call",
        attributes={"agentteam.member.name": "coding-agent"},
        status={"code": "STATUS_CODE_OK"},
        tool_call={
            "name": "shell",
            "id": "call-1",
            "input": {"command": "python test.py"},
            "output": {"exit_code": 0},
        },
    )
    assert tool_event is not None
    assert tool_event.kind is TrajectoryEventKind.TOOL
    assert tool_event.name == "shell"

    print("OPENJIUWEN_TRAJECTORY_MAPPING_OK")
    print("TRAJECTORY_SCHEMA_OK")
    print("TRAJECTORY_USAGE_ACCOUNTING_OK")
    print("TRAJECTORY_SEQUENCE_GUARD_OK")


if __name__ == "__main__":
    asyncio.run(main())
