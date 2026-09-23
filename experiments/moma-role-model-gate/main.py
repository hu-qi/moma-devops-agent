"""Capability probe for candidate MoMA AgentTeam role models.

By default this script reports eligibility without failing the workflow.
Set ROLE_MODEL_GATE_STRICT=1 when validating a model that is required by the
current DevOpsPilot role configuration.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from openjiuwen.core.foundation.llm import Model, ModelClientConfig, ModelRequestConfig


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def probe_model(model_id: str) -> dict[str, Any]:
    model = Model(
        model_client_config=ModelClientConfig(
            client_provider="OpenAI",
            api_base=required("MOMA_API_BASE"),
            api_key=required("MOMA_API_KEY"),
            endpoint_profile="openai_compatible",
            timeout=180,
        ),
        model_config=ModelRequestConfig(
            model=model_id,
            temperature=0,
        ),
    )

    basic = await model.invoke(messages=[{
        "role": "user",
        "content": "Reply with exactly ROLE_MODEL_BASIC_OK",
    }])
    basic_text = (getattr(basic, "content", "") or "").strip()

    tools = [{
        "type": "function",
        "function": {
            "name": "inspect_repository",
            "description": "Inspect one repository file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }]

    try:
        tool_response = await model.invoke(
            messages=[{
                "role": "user",
                "content": (
                    "You must call inspect_repository with path='src/app.py'. "
                    "Do not answer without the tool call."
                ),
            }],
            tools=tools,
        )
        calls = getattr(tool_response, "tool_calls", None) or []
        tool_ok = bool(calls)
        finish_reason = getattr(tool_response, "finish_reason", None)
        tool_calls = [str(call) for call in calls]
        tool_error = None
    except Exception as exc:
        tool_ok = False
        finish_reason = None
        tool_calls = []
        tool_error = f"{type(exc).__name__}: {exc}"

    marker = "ROLE_MODEL_BASIC_OK"
    report: dict[str, Any] = {
        "model": model_id,
        "basic_ok": marker in basic_text,
        "basic_exact": basic_text == marker,
        "basic_contains_think_tag": "<think>" in basic_text.lower(),
        "basic_text": basic_text[:200],
        "tool_calling_ok": tool_ok,
        "finish_reason": finish_reason,
        "tool_calls": tool_calls,
        "tool_error": tool_error,
    }
    report["agentteam_role_eligible"] = bool(
        report["basic_ok"] and report["tool_calling_ok"]
    )
    return report


async def main() -> None:
    model_id = required("ROLE_MODEL_ID")
    report = await probe_model(model_id)
    print("ROLE_MODEL_REPORT=" + json.dumps(report, ensure_ascii=False))

    if report["agentteam_role_eligible"]:
        if not report["basic_exact"]:
            print(
                "ROLE_MODEL_NOTE=basic response contains extra model-native "
                "reasoning/content; structured tool calling remains eligible"
            )
        return

    message = (
        f"Model {model_id} is not eligible for tool-using AgentTeam roles "
        "under the current OpenAI-compatible MoMA endpoint"
    )
    if truthy("ROLE_MODEL_GATE_STRICT"):
        raise SystemExit(message)

    print("ROLE_MODEL_INELIGIBLE=" + message)


if __name__ == "__main__":
    asyncio.run(main())
