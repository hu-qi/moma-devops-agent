"""File-backed persistent store for canonical delivery trajectories (C10).

The canonical trajectory is an audit artifact: it must be saved to disk next
to the delivery state so the final verifier can confirm the evidence actually
exists and matches the execution metadata, instead of trusting metadata
declarations alone.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from devopspilot.contracts.trajectory import (
    DeliveryTrajectory,
    TrajectoryEvent,
    TrajectoryEventKind,
)


class TrajectoryEvidenceError(RuntimeError):
    """Raised when a claimed trajectory cannot be loaded as real evidence."""


def _event_kind(value: str) -> TrajectoryEventKind:
    try:
        return TrajectoryEventKind(value)
    except ValueError:
        return TrajectoryEventKind.AGENT


class FileTrajectoryStore:
    """Stores canonical trajectories as JSON files, one per trajectory id."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._lock = asyncio.Lock()

    def path_for(self, trajectory_id: str) -> Path:
        safe = trajectory_id.replace("/", "_").replace("\\", "_")
        return self._root / f"{safe}.json"

    async def save(self, trajectory: DeliveryTrajectory) -> Path:
        payload = {
            "trajectory_id": trajectory.trajectory_id,
            "task_id": trajectory.task_id,
            "repository": trajectory.repository,
            "event_count": len(trajectory.events),
            "events": [
                {
                    "sequence": event.sequence,
                    "kind": getattr(event.kind, "value", str(event.kind)),
                    "name": event.name,
                    "status": event.status,
                    "attributes": dict(event.attributes),
                }
                for event in trajectory.events
            ],
        }
        async with self._lock:
            self._root.mkdir(parents=True, exist_ok=True)
            path = self.path_for(trajectory.trajectory_id)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
            return path

    async def load(self, trajectory_id: str) -> DeliveryTrajectory:
        path = self.path_for(trajectory_id)
        async with self._lock:
            if not path.is_file():
                raise TrajectoryEvidenceError(
                    f"Trajectory evidence file not found for id '{trajectory_id}': {path}"
                )
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise TrajectoryEvidenceError(
                    f"Trajectory evidence file for '{trajectory_id}' is unreadable: {exc}"
                ) from exc
        events = tuple(
            TrajectoryEvent(
                sequence=int(item.get("sequence", 0)),
                kind=_event_kind(str(item.get("kind", ""))),
                name=str(item.get("name", "")),
                status=str(item.get("status", "")),
                attributes=dict(item.get("attributes", {})),
            )
            for item in data.get("events", ())
        )
        return DeliveryTrajectory(
            trajectory_id=str(data.get("trajectory_id", trajectory_id)),
            task_id=str(data.get("task_id", "")),
            repository=str(data.get("repository", "")),
            events=events,
        )
