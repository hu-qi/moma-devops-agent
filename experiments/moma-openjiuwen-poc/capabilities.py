"""Extended MoMA capability probes through OpenJiuwen 0.1.19.

Required baseline:
- streaming must produce text

Capability discovery:
- tool calling is recorded as supported/unsupported without hiding the reason
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from openjiuwen.core.foundation.llm import Model, ModelClientConfig, ModelRequestConfig


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_model() -> Model:
    return Model(
        model_client_config=ModelClientConfig(
            client_provider="OpenAI",
            api_base=required_env("MOMA_API_BASE"),
            api_key=required_env("MOMA_API_KEY"),
            endpoint_profile="openai_compatible",
            timeout=float(os.getenv("MOMA_TIMEOUT", "120")),
        ),
        model_config=ModelRequestConfig(
            model=required_env("MOMA_MODEL"),
            temperature=0,
        ),
    )


async def probe_streaming(model: Model) -> dict[str, Any]:
    chunks: list[str] = []
    chunk_count = 0
    async for chunk in model.stream(
        messages=[
            {
                "role": "user",
                "content": "Reply with exactly: MOMA_STREAM_OK",
            }
        ]
    ):
        chunk_count += 1
        if getattr(chunk, "content", None):
            chunks.append(chunk.content)

    text = "".join(chunks).strip()
    return {
        "supported": text == "MOMA_STREAM_OK",
        "chunk_count": chunk_count,
        "text": text,
    }


async def probe_tool_calling(model: Model) -> dict[str, Any]:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_build_status",
                "description": "Get the CI build status for a numeric run id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "run_id": {
                            "type": "integer",
                            "description": "CI run id",
                        }
                    },
                    "required": ["run_id"],
                    "additionalProperties": False,
                },
            },
        }
    ]

    try:
        response = await model.invoke(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You must call get_build_status for run_id 42. "
                        "Do not answer the status yourself."
                    ),
                }
            ],
            tools=tools,
        )
        calls = getattr(response, "tool_calls", None) or []
        serialized = [str(call) for call in calls]
        return {
            "supported": bool(calls),
            "finish_reason": getattr(response, "finish_reason", None),
            "tool_calls": serialized,
            "content": getattr(response, "content", None),
        }
    except Exception as exc:  # capability probe: preserve evidence, do not mask
        return {
            "supported": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


async def main() -> None:
    model = build_model()
    report = {
        "model": required_env("MOMA_MODEL"),
        "streaming": await probe_streaming(model),
        "tool_calling": await probe_tool_calling(model),
    }
    print("=== MoMA capability report ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if not report["streaming"]["supported"]:
        raise SystemExit("Streaming probe failed")


if __name__ == "__main__":
    asyncio.run(main())
