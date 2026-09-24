"""Durable service facade for autonomous CI remediation."""

from __future__ import annotations

from devopspilot.contracts.state import DeliveryStateStore, StoredDeliveryState
from .control_plane import AutonomousDeliveryControlPlane


class AutonomousDeliveryOrchestrator:
    def __init__(
        self,
        *,
        control_plane: AutonomousDeliveryControlPlane,
        store: DeliveryStateStore,
    ) -> None:
        self._control_plane = control_plane
        self._store = store

    async def remediate_ci_failure(self, delivery_id: str) -> StoredDeliveryState:
        current = await self._store.load(delivery_id)
        if current is None:
            raise KeyError(f"Unknown delivery_id: {delivery_id}")
        next_state = await self._control_plane.handle_ci_failure(
            delivery_id,
            current.state,
        )
        return await self._store.save(
            delivery_id,
            next_state,
            expected_version=current.version,
        )
