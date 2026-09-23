"""Persistence contract for resumable delivery state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .delivery import DeliveryState


class DeliveryStateConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StoredDeliveryState:
    delivery_id: str
    version: int
    state: DeliveryState


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
