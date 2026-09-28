"""Execution-plane contracts below DeliveryLoop and above Agent runtimes."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Protocol, runtime_checkable

from .delivery import DeliveryTask, ExecutionResult
from .review import (
    MissingReviewError,
    ReviewFinding,
    ReviewGateError,
    ReviewRejectedError,
    ReviewResult,
    ReviewTimeoutError,
    ReviewVerdict,
    StaleReviewError,
    enforce_review_gate,
)

__all__ = (
    "ExecutionWorkspace",
    "WorkspaceProvider",
    "ChangePublisher",
    "ReviewVerdict",
    "ReviewFinding",
    "ReviewResult",
    "ReviewGateError",
    "MissingReviewError",
    "ReviewRejectedError",
    "StaleReviewError",
    "ReviewTimeoutError",
    "enforce_review_gate",
)


@dataclass(frozen=True, slots=True)
class ExecutionWorkspace:
    path: Path
    source_branch: str
    base_commit: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class WorkspaceProvider(Protocol):
    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        ...

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        ...


@runtime_checkable
class ChangePublisher(Protocol):
    """Publish a locally committed ExecutionResult to its SCM provider."""

    async def publish(
        self,
        task: DeliveryTask,
        result: ExecutionResult,
    ) -> ExecutionResult:
        ...
