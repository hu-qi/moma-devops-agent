"""SQLite ledger for bounded CI remediation attempts."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

from devopspilot.contracts.remediation import (
    CIFailureKind,
    RemediationAction,
    RemediationLedger,
    RemediationOutcome,
    RemediationRecord,
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
                    PRIMARY KEY (delivery_id, attempt)
                )
                """
            )

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
            )
            for row in rows
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
