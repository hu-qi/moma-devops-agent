"""Service and adapter assembly for DevOpsPilot CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from devopspilot.contracts.delivery import (
    DeliveryState,
    DeliveryVerifier,
    TaskExecutor,
)
from devopspilot.contracts.providers import CIProvider, SCMProvider
from devopspilot.contracts.state import DeliveryStateStore
from devopspilot.orchestration.delivery_loop import DeliveryLoop
from devopspilot.orchestration.service import DeliveryOrchestrator
from devopspilot.orchestration.verifier import StandardDeliveryVerifier
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore


@dataclass(frozen=True, slots=True)
class AppConfig:
    db_path: Path
    provider: str = "mock"
    default_target_branch: str = "main"
    execution_mode: str = "single_agent"
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    test_command: str = ""
    require_review: bool = True
    required_checks: tuple[str, ...] = ()
    extra_metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        db = Path(data.get("db_path", ".devopspilot/state.db"))
        return cls(
            db_path=db,
            provider=str(data.get("provider", "mock")),
            default_target_branch=str(data.get("default_target_branch", "main")),
            execution_mode=str(data.get("execution_mode", "single_agent")),
            allowed_paths=tuple(data.get("allowed_paths", ())),
            forbidden_paths=tuple(data.get("forbidden_paths", ())),
            test_command=str(data.get("test_command", "")),
            require_review=bool(data.get("require_review", True)),
            required_checks=tuple(data.get("required_checks", ())),
            extra_metadata=dict(data.get("extra_metadata", {})),
        )


def assemble_orchestrator(
    config: AppConfig,
    *,
    scm: SCMProvider | None = None,
    ci: CIProvider | None = None,
    executor: TaskExecutor | None = None,
    verifier: DeliveryVerifier | None = None,
    store: DeliveryStateStore | None = None,
) -> DeliveryOrchestrator:
    """Assemble a runnable DeliveryOrchestrator from config with pluggable components."""
    # Ensure database parent directory exists
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    state_store = store or SQLiteDeliveryStateStore(config.db_path)
    deliv_verifier = verifier or StandardDeliveryVerifier()

    if scm is None or ci is None or executor is None:
        raise ValueError("scm, ci, and executor adapters must be supplied for orchestrator assembly")

    loop = DeliveryLoop(
        scm=scm,
        ci=ci,
        executor=executor,
        verifier=deliv_verifier,
    )
    return DeliveryOrchestrator(loop=loop, store=state_store)
