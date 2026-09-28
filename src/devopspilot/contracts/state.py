"""Persistence contract for resumable delivery state and execution leases."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable

from .delivery import DeliveryState


class DeliveryStateConflict(RuntimeError):
    pass


class LeaseAcquisitionError(RuntimeError):
    pass


class IntentStatus(StrEnum):
    ACQUIRED = "acquired"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class StoredDeliveryState:
    delivery_id: str
    version: int
    state: DeliveryState


@dataclass(frozen=True, slots=True)
class LeaseAcquireResult:
    acquired: bool
    delivery_id: str
    existing_state: StoredDeliveryState | None = None
    lease_token: str = ""
    status: IntentStatus = IntentStatus.ACQUIRED
    message: str = ""


@runtime_checkable
class DeliveryStateStore(Protocol):
    async def load(self, delivery_id: str) -> StoredDeliveryState | None:
        ...

    async def save(
        self,
        delivery_id: str,
        state: DeliveryState,
        *,
        expected_version: int | None = None,
    ) -> StoredDeliveryState:
        ...

    async def acquire_lease(
        self,
        deduplication_key: str,
        delivery_id: str,
        *,
        owner: str = "worker",
        ttl_seconds: float = 300.0,
    ) -> LeaseAcquireResult:
        """Attempt to acquire execution lease for deduplication_key atomically."""
        ...

    async def release_lease(
        self,
        deduplication_key: str,
        lease_token: str,
    ) -> None:
        """Release lease early if execution finishes or fails."""
        ...

    async def complete_intent(
        self,
        deduplication_key: str,
        delivery_id: str,
    ) -> None:
        """Mark intent as completed once side-effects and initial state are persisted."""
        ...
