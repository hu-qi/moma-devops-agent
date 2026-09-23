"""Dynamic AgentTeam spike for DevOpsPilot.

Goal:
- use MoMA through OpenJiuwen
- start one DevOps Leader
- let the Leader dynamically form a Coding + Review team
- keep the team runtime disposable and isolated
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from openjiuwen.agent_teams import TeamAgentSpec
from openjiuwen.core.runner import Runner


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def model_spec(model_name: str) -> dict:
    return {
        "model": {
            "model_client_config": {
                "client_provider": "OpenAI",
                "api_key": required_env("MOMA_API_KEY"),
                "api_base": required_env("MOMA_API_BASE"),
                "endpoint_profile": "openai_compatible",
                "timeout": 120,
            },
            "model_request_config": {
                "model": model_name,
                "temperature": 0.1,
                "top_p": 0.9,
            },
        },
        "max_iterations": 40,
        "completion_timeout": 600.0,
    }


def build_spec(workspace: Path) -> TeamAgentSpec:
    default_model = required_env("MOMA_MODEL")
    leader_model = os.getenv("MOMA_REASONING_MODEL", default_model).strip() or default_model
    teammate_model = os.getenv("MOMA_CODING_MODEL", default_model).strip() or default_model

    cfg = {
        "agents": {
            "leader": model_spec(leader_model),
            "teammate": model_spec(teammate_model),
        },
        "transport": {"type": "inprocess"},
        "storage": {
            "type": "sqlite",
            "params": {
                "connection_string": str(workspace / "team.db"),
            },
        },
        "team_name": "devopspilot-spike-team",
        "lifecycle": "temporary",
        "teammate_mode": "build_mode",
        "spawn_mode": "inprocess",
        "leader": {
            "member_name": "devops_leader",
            "display_name": "DevOps Leader",
            "persona": (
                "You are the DevOpsPilot leader. For this spike, do not solve the task alone. "
                "Initialize a team, dynamically create exactly two specialist teammates: "
                "coding_agent and review_agent. Give them distinct responsibilities. "
                "The coding agent proposes a patch plan; the review agent independently "
                "checks correctness and risk. Then synthesize a final delivery decision."
            ),
        },
    }
    return TeamAgentSpec.model_validate(cfg)


async def main() -> None:
    workspace = Path(tempfile.mkdtemp(prefix="devopspilot_agent_team_")).resolve()
    spec = build_spec(workspace)

    query = """
We are validating the team topology, not modifying a real repository.

Task:
A Python service crashes when an environment variable PORT is missing because
the code uses os.environ["PORT"] and converts it to int.

Requirements:
1. Dynamically create coding_agent and review_agent.
2. coding_agent should propose a minimal robust implementation and tests.
3. review_agent should independently identify regressions or edge cases.
4. The leader must report each member's responsibility and give the final
   recommended patch only after considering the review.
"""

    await Runner.start()
    try:
        async for chunk in Runner.run_agent_team_streaming(
            agent_team=spec,
            inputs={"query": query},
            session="devopspilot-agent-team-spike",
        ):
            print(chunk, end="", flush=True)
    finally:
        await Runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
