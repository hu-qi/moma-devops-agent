"""OpenJiuwen RSI integration-surface smoke for DevOpsPilot.

This is deliberately NOT an optimization benchmark.
It verifies that:
1. the installed runtime exposes the expected RSI surface;
2. a MoMA-backed OpenJiuwen Model can be injected into AutoHarnessConfig;
3. an AutoHarnessOrchestrator can be constructed in an isolated temp workspace.

A real RSI improvement claim requires DevOpsBench baseline/candidate comparison.
"""

from __future__ import annotations

import json
import os
import tempfile
from importlib import metadata
from pathlib import Path

from openjiuwen.core.foundation.llm import Model, ModelClientConfig, ModelRequestConfig
from openjiuwen.rsi import (
    AutoHarnessConfig,
    MemberOptimizer,
    ProgramArtifactProvider,
    SingleHarnessIterativeOptimizationOrchestrator,
    TeamEvaluator,
    create_auto_harness_orchestrator,
)


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
            timeout=120,
        ),
        model_config=ModelRequestConfig(
            model=required_env("MOMA_MODEL"),
            temperature=0,
        ),
    )


def public_methods(obj: object) -> list[str]:
    return sorted(
        name
        for name in dir(obj)
        if not name.startswith("_") and callable(getattr(obj, name, None))
    )


def main() -> None:
    model = build_model()

    with tempfile.TemporaryDirectory(prefix="devopspilot_rsi_") as td:
        data_dir = Path(td) / "rsi-data"
        data_dir.mkdir(parents=True, exist_ok=True)

        config = AutoHarnessConfig(
            model=model,
            data_dir=str(data_dir),
            local_repo=str(Path.cwd()),
            language="en",
            optimization_goal=(
                "Validate DevOpsPilot's controlled RSI integration boundary. "
                "Do not mutate or publish repository changes in this smoke test."
            ),
            max_tasks_per_session=1,
            cost_limit_usd=0.01,
        )
        orchestrator = create_auto_harness_orchestrator(config)

        report = {
            "openjiuwen_version": metadata.version("openjiuwen"),
            "rsi_surface_available": True,
            "moma_model_injected": config.model is model,
            "data_dir_is_temporary": str(data_dir).startswith(td),
            "orchestrator_type": type(orchestrator).__name__,
            "orchestrator_public_methods": public_methods(orchestrator),
            "confirmed_symbols": [
                TeamEvaluator.__name__,
                MemberOptimizer.__name__,
                ProgramArtifactProvider.__name__,
                SingleHarnessIterativeOptimizationOrchestrator.__name__,
            ],
            "optimization_executed": False,
            "reason": (
                "A real optimization is deferred until DevOpsBench provides "
                "baseline, candidate and regression gates."
            ),
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
