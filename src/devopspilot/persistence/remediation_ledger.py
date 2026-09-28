"""SQLite ledger for bounded CI remediation attempts."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path

from devopspilot.contracts.remediation import (
    CIFailureKind,
    RemediationAction,
    RemediationLedger,
    RemediationOutcome,
    RemediationRecord,
    RemediationStatus,
)


class RemediationLedgerConflict(RuntimeError):
    pass


class SQLiteRemediationLedger(RemediationLedger):
    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS remediation_attempt (
                    delivery_id TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    failure_kind TEXT NOT NULL,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    previous_commit_sha TEXT NOT NULL,
                    resulting_commit_sha TEXT,
                    evidence TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'completed',
                    error_message TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL DEFAULT 0.0,
                    updated_at REAL NOT NULL DEFAULT 0.0,
                    PRIMARY KEY (delivery_id, attempt)
                )
                """
            )
            # Add columns if table already existed without them
            try:
                db.execute("ALTER TABLE remediation_attempt ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'")
            except sqlite3.OperationalError:
                pass
            try:
                db.execute("ALTER TABLE remediation_attempt ADD COLUMN error_message TEXT NOT NULL DEFAULT ''")
            except sqlite3.OperationalError:
                pass
            try:
                db.execute("ALTER TABLE remediation_attempt ADD COLUMN created_at REAL NOT NULL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass
            try:
                db.execute("ALTER TABLE remediation_attempt ADD COLUMN updated_at REAL NOT NULL DEFAULT 0.0")
            except sqlite3.OperationalError:
                pass

    async def list(self, delivery_id: str) -> tuple[RemediationRecord, ...]:
        return await asyncio.to_thread(self._list_sync, delivery_id)

    def _list_sync(self, delivery_id: str) -> tuple[RemediationRecord, ...]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM remediation_attempt WHERE delivery_id = ? "
                "ORDER BY attempt ASC",
                (delivery_id,),
            ).fetchall()
        return tuple(
            RemediationRecord(
                delivery_id=row["delivery_id"],
                attempt=int(row["attempt"]),
                failure_kind=CIFailureKind(row["failure_kind"]),
                action=RemediationAction(row["action"]),
                outcome=RemediationOutcome(row["outcome"]),
                summary=row["summary"],
                previous_commit_sha=row["previous_commit_sha"],
                resulting_commit_sha=row["resulting_commit_sha"],
                evidence=tuple(json.loads(row["evidence"])),
                status=RemediationStatus(row["status"]) if "status" in row.keys() else RemediationStatus.COMPLETED,
                error_message=row["error_message"] if "error_message" in row.keys() else "",
                created_at=float(row["created_at"]) if "created_at" in row.keys() else 0.0,
                updated_at=float(row["updated_at"]) if "updated_at" in row.keys() else 0.0,
            )
            for row in rows
        )

    async def reserve_attempt(
        self,
        delivery_id: str,
        attempt: int,
        failure_kind: CIFailureKind,
        action: RemediationAction,
        previous_commit_sha: str,
        evidence: tuple[str, ...] = (),
    ) -> RemediationRecord:
        return await asyncio.to_thread(
            self._reserve_attempt_sync,
            delivery_id,
            attempt,
            failure_kind,
            action,
            previous_commit_sha,
            evidence,
        )

    def _reserve_attempt_sync(
        self,
        delivery_id: str,
        attempt: int,
        failure_kind: CIFailureKind,
        action: RemediationAction,
        previous_commit_sha: str,
        evidence: tuple[str, ...],
    ) -> RemediationRecord:
        now = time.time()
        record = RemediationRecord(
            delivery_id=delivery_id,
            attempt=attempt,
            failure_kind=failure_kind,
            action=action,
            outcome=RemediationOutcome.PENDING,
            summary=f"Attempt {attempt} reserved for {action.value}",
            previous_commit_sha=previous_commit_sha,
            resulting_commit_sha=None,
            evidence=evidence,
            status=RemediationStatus.RUNNING,
            error_message="",
            created_at=now,
            updated_at=now,
        )
        try:
            with self._connect() as db:
                db.execute(
                    """
                    INSERT INTO remediation_attempt(
                        delivery_id, attempt, failure_kind, action, outcome,
                        summary, previous_commit_sha, resulting_commit_sha, evidence,
                        status, error_message, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.delivery_id,
                        record.attempt,
                        record.failure_kind.value,
                        record.action.value,
                        record.outcome.value,
                        record.summary,
                        record.previous_commit_sha,
                        record.resulting_commit_sha,
                        json.dumps(list(record.evidence), ensure_ascii=False),
                        record.status.value,
                        record.error_message,
                        record.created_at,
                        record.updated_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RemediationLedgerConflict(
                f"duplicate remediation attempt {delivery_id}:{attempt}"
            ) from exc
        return record

    async def update(self, record: RemediationRecord) -> None:
        await asyncio.to_thread(self._update_sync, record)

    def _update_sync(self, record: RemediationRecord) -> None:
        now = time.time()
        with self._connect() as db:
            db.execute(
                """
                UPDATE remediation_attempt SET
                    outcome = ?,
                    summary = ?,
                    resulting_commit_sha = ?,
                    status = ?,
                    error_message = ?,
                    updated_at = ?
                WHERE delivery_id = ? AND attempt = ?
                """,
                (
                    record.outcome.value,
                    record.summary,
                    record.resulting_commit_sha,
                    record.status.value,
                    record.error_message,
                    now,
                    record.delivery_id,
                    record.attempt,
                ),
            )

    async def append(self, record: RemediationRecord) -> None:
        await asyncio.to_thread(self._append_sync, record)

    def _append_sync(self, record: RemediationRecord) -> None:
        try:
            with self._connect() as db:
                db.execute(
                    """
                    INSERT INTO remediation_attempt(
                        delivery_id, attempt, failure_kind, action, outcome,
                        summary, previous_commit_sha, resulting_commit_sha, evidence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.delivery_id,
                        record.attempt,
                        record.failure_kind.value,
                        record.action.value,
                        record.outcome.value,
                        record.summary,
                        record.previous_commit_sha,
                        record.resulting_commit_sha,
                        json.dumps(list(record.evidence), ensure_ascii=False),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RemediationLedgerConflict(
                f"duplicate remediation attempt {record.delivery_id}:{record.attempt}"
            ) from exc
