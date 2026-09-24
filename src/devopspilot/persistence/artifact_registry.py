"""Versioned SQLite registry for governed evolution artifacts."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    EvolutionCandidate,
    PromotionDecision,
    RollbackDecision,
)


class ArtifactRegistryConflict(RuntimeError):
    pass


class SQLiteArtifactRegistry:
    """Control-plane registry for staged/active evolution artifacts.

    This registry never writes runtime Skill/Prompt files. Activation is only a
    versioned control-plane pointer. Runtime materialization is a separate port.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifact_version (
                    artifact_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    source_candidate_id TEXT,
                    PRIMARY KEY(artifact_id, version)
                );

                CREATE TABLE IF NOT EXISTS artifact_active (
                    artifact_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS artifact_activation_history (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id TEXT NOT NULL,
                    version TEXT,
                    action TEXT NOT NULL,
                    decided_by TEXT NOT NULL,
                    reason TEXT NOT NULL
                );
                """
            )

    async def register_baseline(self, artifact: ArtifactVersion) -> ArtifactVersion:
        return await asyncio.to_thread(
            self._register_version_sync,
            artifact,
            None,
        )

    async def stage_candidate(
        self,
        candidate: EvolutionCandidate,
    ) -> ArtifactVersion:
        return await asyncio.to_thread(
            self._register_version_sync,
            candidate.artifact,
            candidate.candidate_id,
        )

    def _register_version_sync(
        self,
        artifact: ArtifactVersion,
        source_candidate_id: str | None,
    ) -> ArtifactVersion:
        metadata = json.dumps(
            dict(artifact.metadata),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with self._connect() as db:
            row = db.execute(
                """
                SELECT kind, content, metadata, digest, source_candidate_id
                FROM artifact_version
                WHERE artifact_id = ? AND version = ?
                """,
                (artifact.artifact_id, artifact.version),
            ).fetchone()
            expected = (
                artifact.kind.value,
                artifact.content,
                metadata,
                artifact.digest,
                source_candidate_id,
            )
            if row is None:
                db.execute(
                    """
                    INSERT INTO artifact_version(
                        artifact_id, version, kind, content, metadata, digest,
                        source_candidate_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact.artifact_id,
                        artifact.version,
                        *expected,
                    ),
                )
                return artifact

            actual = (
                row["kind"],
                row["content"],
                row["metadata"],
                row["digest"],
                row["source_candidate_id"],
            )
            if actual != expected:
                raise ArtifactRegistryConflict(
                    f"artifact version {artifact.artifact_id}@{artifact.version} "
                    "already exists with different immutable content"
                )
        return artifact

    async def promote(
        self,
        candidate: EvolutionCandidate,
        decision: PromotionDecision,
        *,
        decided_by: str,
    ) -> ArtifactVersion:
        if decision.candidate_id != candidate.candidate_id:
            raise ArtifactRegistryConflict("promotion decision does not match candidate")
        if decision.state is not ApprovalState.APPROVED:
            raise PermissionError("artifact promotion requires explicit APPROVED decision")
        if not decision.evidence.gate_passed:
            raise PermissionError("artifact promotion requires a passed automated gate")
        if not decided_by.strip():
            raise ValueError("decided_by is required for promotion")

        await self.stage_candidate(candidate)
        await asyncio.to_thread(
            self._activate_sync,
            candidate.artifact.artifact_id,
            candidate.artifact.version,
            "promote",
            decided_by,
            decision.reason,
        )
        return candidate.artifact

    async def rollback(self, decision: RollbackDecision) -> ArtifactVersion | None:
        if decision.state is not ApprovalState.APPROVED:
            raise PermissionError("rollback requires explicit APPROVED decision")
        if not decision.decided_by.strip():
            raise ValueError("decided_by is required for rollback")

        if decision.target_version is None:
            await asyncio.to_thread(
                self._deactivate_sync,
                decision.artifact_id,
                decision.decided_by,
                decision.reason,
            )
            return None

        artifact = await self.load_version(
            decision.artifact_id,
            decision.target_version,
        )
        if artifact is None:
            raise ArtifactRegistryConflict(
                f"unknown rollback target "
                f"{decision.artifact_id}@{decision.target_version}"
            )
        await asyncio.to_thread(
            self._activate_sync,
            decision.artifact_id,
            decision.target_version,
            "rollback",
            decision.decided_by,
            decision.reason,
        )
        return artifact

    async def get_active(self, artifact_id: str) -> ArtifactVersion | None:
        return await asyncio.to_thread(self._get_active_sync, artifact_id)

    def _get_active_sync(self, artifact_id: str) -> ArtifactVersion | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT version FROM artifact_active WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            return None
        return self._load_version_sync(artifact_id, row["version"])

    async def load_version(
        self,
        artifact_id: str,
        version: str,
    ) -> ArtifactVersion | None:
        return await asyncio.to_thread(
            self._load_version_sync,
            artifact_id,
            version,
        )

    def _load_version_sync(
        self,
        artifact_id: str,
        version: str,
    ) -> ArtifactVersion | None:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT kind, content, metadata
                FROM artifact_version
                WHERE artifact_id = ? AND version = ?
                """,
                (artifact_id, version),
            ).fetchone()
        if row is None:
            return None
        return ArtifactVersion(
            artifact_id=artifact_id,
            kind=ArtifactKind(row["kind"]),
            version=version,
            content=row["content"],
            metadata=json.loads(row["metadata"]),
        )

    def _activate_sync(
        self,
        artifact_id: str,
        version: str,
        action: str,
        decided_by: str,
        reason: str,
    ) -> None:
        with self._connect() as db:
            exists = db.execute(
                """
                SELECT 1 FROM artifact_version
                WHERE artifact_id = ? AND version = ?
                """,
                (artifact_id, version),
            ).fetchone()
            if exists is None:
                raise ArtifactRegistryConflict(
                    f"cannot activate unknown artifact {artifact_id}@{version}"
                )
            db.execute(
                """
                INSERT INTO artifact_active(artifact_id, version)
                VALUES (?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET version = excluded.version
                """,
                (artifact_id, version),
            )
            db.execute(
                """
                INSERT INTO artifact_activation_history(
                    artifact_id, version, action, decided_by, reason
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (artifact_id, version, action, decided_by, reason),
            )

    def _deactivate_sync(
        self,
        artifact_id: str,
        decided_by: str,
        reason: str,
    ) -> None:
        with self._connect() as db:
            db.execute(
                "DELETE FROM artifact_active WHERE artifact_id = ?",
                (artifact_id,),
            )
            db.execute(
                """
                INSERT INTO artifact_activation_history(
                    artifact_id, version, action, decided_by, reason
                ) VALUES (?, NULL, 'deactivate', ?, ?)
                """,
                (artifact_id, decided_by, reason),
            )

    async def activation_history(
        self,
        artifact_id: str,
    ) -> tuple[dict[str, Any], ...]:
        return await asyncio.to_thread(
            self._activation_history_sync,
            artifact_id,
        )

    def _activation_history_sync(
        self,
        artifact_id: str,
    ) -> tuple[dict[str, Any], ...]:
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT seq, version, action, decided_by, reason
                FROM artifact_activation_history
                WHERE artifact_id = ?
                ORDER BY seq
                """,
                (artifact_id,),
            ).fetchall()
        return tuple(dict(row) for row in rows)
