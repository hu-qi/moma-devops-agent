"""Contracts for bounded autonomous CI remediation."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
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
    FAILED = "failed"
    PENDING = "pending"


class RemediationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
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
    status: RemediationStatus = RemediationStatus.COMPLETED
    error_message: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0


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
        ...


@runtime_checkable
class RemediationLedger(Protocol):
    async def list(self, delivery_id: str) -> tuple[RemediationRecord, ...]:
        ...

    async def append(self, record: RemediationRecord) -> None:
        ...

    async def reserve_attempt(
        self,
        delivery_id: str,
        attempt: int,
        failure_kind: CIFailureKind,
        action: RemediationAction,
        previous_commit_sha: str,
        evidence: tuple[str, ...] = (),
    ) -> RemediationRecord:
        """Reserve an attempt in the ledger before performing external actions."""
        ...

    async def update(self, record: RemediationRecord) -> None:
        """Update an existing attempt record (e.g. from running to completed/failed)."""
        ...
