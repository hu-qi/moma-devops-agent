"""Bridge OpenJiuwen canonical spans into DevOpsPilot trajectories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from devopspilot.contracts.trajectory import (
    DeliveryTrajectory,
    TrajectoryEvent,
    TrajectoryEventKind,
)


def _status_text(status: Mapping[str, Any] | None) -> str:
    code = str((status or {}).get("code") or "").upper()
    if code in {"2", "ERROR", "STATUS_CODE_ERROR"}:
        return "error"
    if code in {"1", "OK", "STATUS_CODE_OK"}:
        return "success"
    return "success"


def _pick(attrs: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in attrs and attrs[key] is not None:
            return attrs[key]
    return None


def map_openjiuwen_span(
    *,
    sequence: int,
    category: str,
    span_name: str,
    attributes: Mapping[str, Any],
    status: Mapping[str, Any] | None = None,
    usage: Mapping[str, int] | None = None,
    tool_call: Mapping[str, Any] | None = None,
) -> TrajectoryEvent | None:
    """Map one already-decoded OpenJiuwen canonical span.

    This pure function intentionally knows only canonical semantic-convention
    keys. It is independently testable without importing OpenJiuwen.
    """

    normalized = category.lower().strip()
    event_status = _status_text(status)
    common: dict[str, Any] = {}

    member = _pick(
        attributes,
        "agentteam.member.name",
        "gen_ai.agent.name",
        "gen_ai.agent.id",
    )
    if member is not None:
        common["member"] = member

    if normalized == "llm":
        model_id = _pick(
            attributes,
            "gen_ai.response.model",
            "gen_ai.request.model",
            "gen_ai.request.model_name",
        )
        provider = _pick(
            attributes,
            "gen_ai.provider.name",
            "gen_ai.system",
        )
        if model_id is not None:
            common["model_id"] = model_id
        if provider is not None:
            common["provider"] = provider

        usage = usage or {}
        common.update({
            "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "output_tokens": int(usage.get("completion_tokens", 0) or 0),
            "total_tokens": int(usage.get("total_tokens", 0) or 0),
        })

        latency_ms = _pick(
            attributes,
            "openjiuwen.gen_ai.response.total_latency_ms",
        )
        if latency_ms is not None:
            common["latency_ms"] = latency_ms

        return TrajectoryEvent(
            sequence=sequence,
            kind=TrajectoryEventKind.ROUTING,
            name="model.invoke",
            status=event_status,
            attributes=common,
        )

    if normalized == "tool":
        call = dict(tool_call or {})
        tool_name = str(
            call.get("name")
            or _pick(attributes, "gen_ai.tool.name")
            or span_name
            or "unknown"
        )
        if call.get("id") is not None:
            common["tool_call_id"] = call["id"]
        if call.get("input") is not None:
            common["input"] = call["input"]
        if call.get("output") is not None:
            common["output"] = call["output"]
        return TrajectoryEvent(
            sequence=sequence,
            kind=TrajectoryEventKind.TOOL,
            name=tool_name,
            status=event_status,
            attributes=common,
        )

    if normalized in {"agent", "team", "task", "event", "member", "message"}:
        for key, canonical in (
            ("agentteam.agent.role", "role"),
            ("agentteam.task.id", "task_id"),
            ("agentteam.task.status", "task_status"),
            ("agentteam.task.assignee", "task_assignee"),
            ("agentteam.team.name", "team_name"),
        ):
            if attributes.get(key) is not None:
                common[canonical] = attributes[key]
        return TrajectoryEvent(
            sequence=sequence,
            kind=TrajectoryEventKind.AGENT,
            name=span_name or normalized,
            status=event_status,
            attributes=common,
        )

    return None


def openjiuwen_to_delivery_trajectory(
    trajectory: Any,
    *,
    task_id: str,
    repository: str,
) -> DeliveryTrajectory:
    """Convert an OpenJiuwen canonical Trajectory using public accessors."""

    from openjiuwen.agent_evolving.trajectory.spans import (
        iter_spans,
        read_tool_call,
        read_usage,
        span_attributes,
        span_status,
    )
    from openjiuwen.agent_evolving.trajectory.team import span_category

    spans = list(iter_spans(trajectory))
    spans.sort(key=lambda span: (
        int(span.get("startTimeUnixNano") or 0),
        int(span.get("endTimeUnixNano") or 0),
        str(span.get("spanId") or ""),
    ))

    events: list[TrajectoryEvent] = []
    for span in spans:
        category = span_category(span)
        attrs = span_attributes(span)
        event = map_openjiuwen_span(
            sequence=len(events) + 1,
            category=category,
            span_name=str(span.get("name") or category or "span"),
            attributes=attrs,
            status=span_status(span),
            usage=read_usage(span) if category == "llm" else None,
            tool_call=read_tool_call(span) if category == "tool" else None,
        )
        if event is not None:
            events.append(event)

    return DeliveryTrajectory(
        trajectory_id=str(
            getattr(trajectory, "trajectory_id", "") or f"openjiuwen:{task_id}"
        ),
        task_id=task_id,
        repository=repository,
        events=tuple(events),
    )
