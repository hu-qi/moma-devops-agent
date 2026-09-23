"""Inspect the installed OpenJiuwen runtime surface without model credentials.

This smoke test is intentionally introspective. It tells DevOpsPilot which
AgentTeam / RSI symbols are actually present in the installed distribution,
rather than assuming a GitHub branch and a package release are identical.
"""

from __future__ import annotations

import inspect
import json
from importlib import metadata
from typing import Any


def signature_of(value: Any) -> str:
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        return "<signature unavailable>"


def symbol_record(value: Any) -> dict[str, str]:
    return {
        "module": getattr(value, "__module__", ""),
        "qualname": getattr(value, "__qualname__", getattr(value, "__name__", type(value).__name__)),
        "signature": signature_of(value),
    }


def main() -> None:
    version = metadata.version("openjiuwen")

    from openjiuwen.agent_teams import DeepAgentSpec, TeamAgentSpec
    from openjiuwen.core.runner import Runner
    from openjiuwen.harness import create_deep_agent
    from openjiuwen.rsi import (
        AutoHarnessOrchestrator,
        MemberOptimizer,
        ProgramArtifactProvider,
        SingleHarnessIterativeOptimizationOrchestrator,
        TeamEvaluator,
        create_auto_harness_orchestrator,
    )

    symbols = {
        "create_deep_agent": create_deep_agent,
        "Runner": Runner,
        "TeamAgentSpec": TeamAgentSpec,
        "DeepAgentSpec": DeepAgentSpec,
        "AutoHarnessOrchestrator": AutoHarnessOrchestrator,
        "create_auto_harness_orchestrator": create_auto_harness_orchestrator,
        "TeamEvaluator": TeamEvaluator,
        "MemberOptimizer": MemberOptimizer,
        "ProgramArtifactProvider": ProgramArtifactProvider,
        "SingleHarnessIterativeOptimizationOrchestrator": SingleHarnessIterativeOptimizationOrchestrator,
    }

    report = {
        "openjiuwen_version": version,
        "agent_team_available": True,
        "rsi_available": True,
        "symbols": {name: symbol_record(value) for name, value in symbols.items()},
    }

    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
