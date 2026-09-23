"""Minimal MoMA × OpenJiuwen compatibility probe.

This intentionally tests only the model + DeepAgent boundary.
No credentials are stored in the repository.
"""

from __future__ import annotations

import asyncio
import json
import os

from openjiuwen.core.foundation.llm import Model, ModelClientConfig, ModelRequestConfig
from openjiuwen.harness import create_deep_agent


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


async def probe_model(model: Model) -> None:
    response = await model.invoke(
        messages=[
            {
                "role": "user",
                "content": (
                    "This is an API compatibility probe. "
                    "Reply with exactly: MOMA_OPENJIUWEN_OK"
                ),
            }
        ]
    )
    print("=== Model.invoke ===")
    print(response)


async def probe_deep_agent(model: Model) -> None:
    agent = create_deep_agent(
        model=model,
        system_prompt=(
            "You are a minimal compatibility-test agent. "
            "Follow the user's exact output instruction."
        ),
        max_iterations=3,
    )
    result = await agent.invoke(
        {
            "query": (
                "Reply with JSON containing only two fields: "
                '{"status":"ok","runtime":"openjiuwen"}.'
            )
        }
    )
    print("=== DeepAgent.invoke ===")
    print(json.dumps(result, ensure_ascii=False, default=str, indent=2))


async def main() -> None:
    model = build_model()
    await probe_model(model)
    await probe_deep_agent(model)


if __name__ == "__main__":
    asyncio.run(main())
