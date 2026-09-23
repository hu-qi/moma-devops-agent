"""Durable orchestration facade around DeliveryLoop."""

from __future__ import annotations

from devopspilot.contracts.delivery import DeliveryState
from devopspilot.contracts.state import DeliveryStateStore, StoredDeliveryState
from .delivery_loop import DeliveryLoop


class DeliveryOrchestrator:
    def __init__(
        self,
        *,
        loop: DeliveryLoop,
        store: DeliveryStateStore,
    ) -> None:
        self._loop = loop
        self._store = store

    async def start(
        self,
        delivery_id: str,
        *,
        repository_id: str,
        work_item_id: str,
        target_branch: str | None = None,
    ) -> StoredDeliveryState:
        state = await self._loop.start(
            repository_id=repository_id,
            work_item_id=work_item_id,
            target_branch=target_branch,
        )
        return await self._store.save(
            delivery_id,
            state,
            expected_version=0,
        )

    async def reconcile_ci(self, delivery_id: str) -> StoredDeliveryState:
        current = await self._load_required(delivery_id)
        next_state = await self._loop.reconcile_ci(current.state)
        return await self._store.save(
            delivery_id,
            next_state,
            expected_version=current.version,
        )

    async def verify(self, delivery_id: str) -> StoredDeliveryState:
        current = await self._load_required(delivery_id)
        next_state = await self._loop.verify(current.state)
        return await self._store.save(
            delivery_id,
            next_state,
            expected_version=current.version,
        )

    async def get(self, delivery_id: str) -> StoredDeliveryState | None:
        return await self._store.load(delivery_id)

    async def _load_required(self, delivery_id: str) -> StoredDeliveryState:
        stored = await self._store.load(delivery_id)
        if stored is None:
            raise KeyError(f"Unknown delivery_id: {delivery_id}")
        return stored
