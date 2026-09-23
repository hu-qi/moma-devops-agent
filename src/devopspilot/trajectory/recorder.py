"""Simple recorder implementations for canonical trajectories."""

from __future__ import annotations

import asyncio

from devopspilot.contracts.trajectory import DeliveryTrajectory, TrajectoryEvent


class InMemoryTrajectoryRecorder:
    def __init__(
        self,
        *,
        trajectory_id: str,
        task_id: str,
        repository: str,
    ) -> None:
        self._trajectory_id = trajectory_id
        self._task_id = task_id
        self._repository = repository
        self._events: list[TrajectoryEvent] = []
        self._lock = asyncio.Lock()

    async def append(self, event: TrajectoryEvent) -> None:
        async with self._lock:
            if self._events and event.sequence <= self._events[-1].sequence:
                raise ValueError(
                    "trajectory sequence must be strictly increasing"
                )
            self._events.append(event)

    async def snapshot(self) -> DeliveryTrajectory:
        async with self._lock:
            return DeliveryTrajectory(
                trajectory_id=self._trajectory_id,
                task_id=self._task_id,
                repository=self._repository,
                events=tuple(self._events),
            )
