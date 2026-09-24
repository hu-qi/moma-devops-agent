"""Contracts for bounded autonomous CI remediation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from .delivery import DeliveryState, ExecutionResult


class CIFailureKind(StrEnum):
    CODE = "code"
    INFRASTRUCTURE = "infrastructure"
    POLICY = "policy"
    UNKNOWN = "unknown"


class RemediationAction(StrEnum):
    PATCH = "patch"
    RETRY_CI = "retry-ci"
    ESCALATE = "escalate"


class RemediationOutcome(StrEnum):
    COMPLETED = "completed"
    ESCALATED = "escalated"


@dataclass(frozen=True, slots=True)
class CIFailureAnalysis:
    kind: CIFailureKind
    summary: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RemediationRecord:
    delivery_id: str
    attempt: int
    failure_kind: CIFailureKind
    action: RemediationAction
    outcome: RemediationOutcome
    summary: str
    previous_commit_sha: str
    resulting_commit_sha: str | None = None
    evidence: tuple[str, ...] = ()


@runtime_checkable
class CIFailureAnalyzer(Protocol):
    async def analyze(self, state: DeliveryState) -> CIFailureAnalysis:
        ...


@runtime_checkable
class RemediationExecutor(Protocol):
    async def remediate(
        self,
        state: DeliveryState,
        analysis: CIFailureAnalysis,
        *,
        attempt: int,
    ) -> ExecutionResult:
        """Publish a repair commit to the existing source branch."""
        ...


@runtime_checkable
class RemediationLedger(Protocol):
    async def list(self, delivery_id: str) -> tuple[RemediationRecord, ...]:
        ...

    async def append(self, record: RemediationRecord) -> None:
        ...
