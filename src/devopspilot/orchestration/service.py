"""Durable orchestration facade around DeliveryLoop."""

from __future__ import annotations

from typing import Mapping

from devopspilot.contracts.delivery import DeliveryPhase, DeliveryState
from devopspilot.contracts.state import (
    DeliveryStateStore,
    LeaseAcquisitionError,
    StoredDeliveryState,
)
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
        deduplication_key: str | None = None,
        task_metadata: Mapping[str, str] | None = None,
        owner: str = "worker",
        lease_ttl_seconds: float = 300.0,
    ) -> StoredDeliveryState:
        dedup_key = deduplication_key or f"{repository_id}:{work_item_id}:{target_branch or 'default'}"

        lease = await self._store.acquire_lease(
            dedup_key,
            delivery_id,
            owner=owner,
            ttl_seconds=lease_ttl_seconds,
        )

        if not lease.acquired:
            # If the task already executed and has state, return it immediately without secondary side effects
            if lease.existing_state is not None:
                return lease.existing_state
            raise LeaseAcquisitionError(
                f"Cannot acquire execution lease for {dedup_key}: {lease.message} (held by task {lease.delivery_id})"
            )

        try:
            # Checkpoint 1: RECEIVED
            initial_state = await self._loop.prepare_task(
                repository_id=repository_id,
                work_item_id=work_item_id,
                target_branch=target_branch,
                task_metadata=task_metadata,
            )
            saved_1 = await self._store.save(
                lease.delivery_id,
                initial_state,
                expected_version=0 if lease.existing_state is None else lease.existing_state.version,
            )

            # Checkpoint 2: EXECUTED (local commit produced, not yet opened PR)
            executed_state = await self._loop.step_execute(saved_1.state)
            saved_2 = await self._store.save(
                lease.delivery_id,
                executed_state,
                expected_version=saved_1.version,
            )

            # Checkpoint 3: CHANGE_OPENED (PR created, comment added)
            opened_state = await self._loop.step_open_change(saved_2.state)
            saved_3 = await self._store.save(
                lease.delivery_id,
                opened_state,
                expected_version=saved_2.version,
            )

            await self._store.complete_intent(dedup_key, lease.delivery_id)
            return saved_3
        except Exception:
            await self._store.release_lease(dedup_key, lease.lease_token)
            raise

    async def resume(
        self,
        delivery_id: str,
        *,
        owner: str = "worker",
        lease_ttl_seconds: float = 300.0,
    ) -> StoredDeliveryState:
        """Resume a delivery from its last saved checkpoint without repeating completed side-effects."""
        current = await self._load_required(delivery_id)
        task = current.state.task
        dedup_key = f"{task.repository.repository_id}:{task.work_item.item_id}:{task.target_branch or 'default'}"

        lease = await self._store.acquire_lease(
            dedup_key,
            delivery_id,
            owner=owner,
            ttl_seconds=lease_ttl_seconds,
        )
        if not lease.acquired and lease.status != "completed":
            raise LeaseAcquisitionError(
                f"Cannot resume delivery {delivery_id}: {lease.message}"
            )

        phase = current.state.phase

        # Terminal phases
        if phase in {DeliveryPhase.VERIFIED, DeliveryPhase.REJECTED}:
            return current

        # From RECEIVED -> execute and open change
        if phase is DeliveryPhase.RECEIVED:
            executed = await self._loop.step_execute(current.state)
            saved_exec = await self._store.save(delivery_id, executed, expected_version=current.version)
            opened = await self._loop.step_open_change(saved_exec.state)
            saved_open = await self._store.save(delivery_id, opened, expected_version=saved_exec.version)
            await self._store.complete_intent(dedup_key, delivery_id)
            return saved_open

        # From EXECUTED -> only open change (do NOT repeat code execution!)
        if phase is DeliveryPhase.EXECUTED:
            opened = await self._loop.step_open_change(current.state)
            saved_open = await self._store.save(delivery_id, opened, expected_version=current.version)
            await self._store.complete_intent(dedup_key, delivery_id)
            return saved_open

        # From CHANGE_OPENED / CI_PENDING -> reconcile CI
        if phase in {DeliveryPhase.CHANGE_OPENED, DeliveryPhase.CI_PENDING}:
            reconciled = await self._loop.reconcile_ci(current.state)
            return await self._store.save(delivery_id, reconciled, expected_version=current.version)

        # From CI_PASSED / CI_FAILED -> verify
        if phase in {DeliveryPhase.CI_PASSED, DeliveryPhase.CI_FAILED}:
            verified = await self._loop.verify(current.state)
            return await self._store.save(delivery_id, verified, expected_version=current.version)

        return current

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
