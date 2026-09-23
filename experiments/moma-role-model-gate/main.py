"""Capability gate for candidate MoMA AgentTeam role models."""

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


async def main() -> None:
    model_id = required("ROLE_MODEL_ID")
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

    report: dict[str, Any] = {
        "model": model_id,
        "basic_ok": basic_text == "ROLE_MODEL_BASIC_OK",
        "basic_text": basic_text[:200],
        "tool_calling_ok": tool_ok,
        "finish_reason": finish_reason,
        "tool_calls": tool_calls,
        "tool_error": tool_error,
    }
    print("ROLE_MODEL_REPORT=" + json.dumps(report, ensure_ascii=False))

    if not report["basic_ok"] or not report["tool_calling_ok"]:
        raise SystemExit(
            f"Model {model_id} is not eligible for AgentTeam role execution"
        )


if __name__ == "__main__":
    asyncio.run(main())
