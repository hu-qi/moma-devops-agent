"""Minimal dynamic AgentTeam smoke for DevOpsPilot.

Requires an OpenAI-compatible endpoint. In the competition path this is MoMA.
The purpose is to validate OpenJiuwen TeamAgentSpec/Runner behavior before
adding DevOps-specific tools and benchmark tasks.
"""

from __future__ import annotations

import asyncio
import os

from openjiuwen.agent_teams import TeamAgentSpec
from openjiuwen.core.runner import Runner


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_spec() -> TeamAgentSpec:
    model_client = {
        "client_provider": "OpenAI",
        "api_key": required_env("MOMA_API_KEY"),
        "api_base": required_env("MOMA_API_BASE"),
        "endpoint_profile": "openai_compatible",
        "timeout": 120,
    }
    model_request = {
        "model": required_env("MOMA_MODEL"),
        "temperature": 0,
    }

    return TeamAgentSpec.model_validate(
        {
            "agents": {
                "leader": {
                    "model": {
                        "model_client_config": model_client,
                        "model_request_config": model_request,
                    },
                    "system_prompt": (
                        "You are the DevOpsPilot Leader. "
                        "For non-trivial tasks, create specialist teammates with narrow roles. "
                        "Always request an independent review before declaring completion."
                    ),
                    "max_iterations": 40,
                    "completion_timeout": 300,
                },
                "teammate": {
                    "model": {
                        "model_client_config": model_client,
                        "model_request_config": model_request,
                    },
                    "max_iterations": 30,
                    "completion_timeout": 240,
                },
            },
            "team_name": "devopspilot_spike",
            "lifecycle": "temporary",
            "teammate_mode": "build_mode",
            "spawn_mode": "inprocess",
            "team_mode": "default",
            "dispatch_mode": "autonomous",
            "enable_task_verification": True,
            "evolution_enabled": True,
            "transport": {"type": "inprocess"},
            "storage": {"type": "memory"},
            "leader": {
                "member_name": "devops_leader",
                "display_name": "DevOps Leader",
                "persona": "software delivery lead",
            },
        }
    )


async def main() -> None:
    spec = build_spec()
    team = spec.build()

    await Runner.start()
    try:
        query = (
            "This is a deterministic AgentTeam capability probe, not a coding task. "
            "Create two specialist teammates: one Coding Analyst and one Reviewer. "
            "Ask the Coding Analyst to propose exactly three checks for a CI build failure. "
            "Ask the Reviewer to independently review those checks and identify one missing risk. "
            "Then return a concise final report with the member roles and final four checks. "
            "Do not use external tools."
        )

        async for chunk in Runner.run_agent_team_streaming(
            agent_team=team,
            inputs={"query": query},
            session="devopspilot-agentteam-spike",
        ):
            print(chunk, end="", flush=True)
    finally:
        await Runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
