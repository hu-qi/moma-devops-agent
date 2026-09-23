"""SQLite persistence for resumable DeliveryState."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
    VerificationResult,
)
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.state import (
    DeliveryStateConflict,
    StoredDeliveryState,
)


class SQLiteDeliveryStateStore:
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
                CREATE TABLE IF NOT EXISTS delivery_state (
                    delivery_id TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )

    async def load(self, delivery_id: str) -> StoredDeliveryState | None:
        return await asyncio.to_thread(self._load_sync, delivery_id)

    def _load_sync(self, delivery_id: str) -> StoredDeliveryState | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT delivery_id, version, payload "
                "FROM delivery_state WHERE delivery_id = ?",
                (delivery_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredDeliveryState(
            delivery_id=row["delivery_id"],
            version=int(row["version"]),
            state=_decode_state(json.loads(row["payload"])),
        )

    async def save(
        self,
        delivery_id: str,
        state: DeliveryState,
        *,
        expected_version: int | None = None,
    ) -> StoredDeliveryState:
        return await asyncio.to_thread(
            self._save_sync,
            delivery_id,
            state,
            expected_version,
        )

    def _save_sync(
        self,
        delivery_id: str,
        state: DeliveryState,
        expected_version: int | None,
    ) -> StoredDeliveryState:
        payload = json.dumps(_encode_state(state), ensure_ascii=False)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT version FROM delivery_state WHERE delivery_id = ?",
                (delivery_id,),
            ).fetchone()
            current = int(row["version"]) if row is not None else 0

            if expected_version is not None and current != expected_version:
                raise DeliveryStateConflict(
                    f"delivery {delivery_id!r} version is {current}, "
                    f"expected {expected_version}"
                )

            next_version = current + 1
            if row is None:
                db.execute(
                    "INSERT INTO delivery_state(delivery_id, version, payload) "
                    "VALUES (?, ?, ?)",
                    (delivery_id, next_version, payload),
                )
            else:
                db.execute(
                    "UPDATE delivery_state SET version = ?, payload = ? "
                    "WHERE delivery_id = ?",
                    (next_version, payload, delivery_id),
                )

        return StoredDeliveryState(
            delivery_id=delivery_id,
            version=next_version,
            state=state,
        )


def _repo(value: dict[str, Any]) -> RepositoryRef:
    return RepositoryRef(**value)


def _encode_state(state: DeliveryState) -> dict[str, Any]:
    task = state.task
    repo = task.repository
    work = task.work_item
    payload: dict[str, Any] = {
        "task": {
            "repository": {
                "provider_id": repo.provider_id,
                "repository_id": repo.repository_id,
                "full_name": repo.full_name,
                "default_branch": repo.default_branch,
                "web_url": repo.web_url,
            },
            "work_item": {
                "item_id": work.item_id,
                "title": work.title,
                "body": work.body,
                "state": work.state,
                "author_id": work.author_id,
                "labels": list(work.labels),
            },
            "target_branch": task.target_branch,
            "metadata": dict(task.metadata),
        },
        "phase": state.phase.value,
        "execution": None,
        "change_request": None,
        "ci_run": None,
        "ci_logs": [],
        "verification": None,
    }

    if state.execution:
        payload["execution"] = {
            "source_branch": state.execution.source_branch,
            "commit_sha": state.execution.commit_sha,
            "summary": state.execution.summary,
            "published": state.execution.published,
            "test_summary": state.execution.test_summary,
            "metadata": dict(state.execution.metadata),
        }

    if state.change_request:
        cr = state.change_request
        payload["change_request"] = {
            "change_id": cr.change_id,
            "title": cr.title,
            "source_branch": cr.source_branch,
            "target_branch": cr.target_branch,
            "state": cr.state,
            "web_url": cr.web_url,
        }

    if state.ci_run:
        run = state.ci_run
        payload["ci_run"] = {
            "provider_id": run.provider_id,
            "run_id": run.run_id,
            "status": run.status,
            "conclusion": run.conclusion,
            "commit_sha": run.commit_sha,
            "web_url": run.web_url,
        }

    payload["ci_logs"] = [
        {
            "job_id": log.job_id,
            "job_name": log.job_name,
            "content": log.content,
        }
        for log in state.ci_logs
    ]

    if state.verification:
        payload["verification"] = {
            "accepted": state.verification.accepted,
            "summary": state.verification.summary,
            "evidence": list(state.verification.evidence),
        }
    return payload


def _decode_state(payload: dict[str, Any]) -> DeliveryState:
    task_data = payload["task"]
    repository = _repo(task_data["repository"])
    work_data = task_data["work_item"]
    work_item = WorkItemRef(
        repository=repository,
        item_id=work_data["item_id"],
        title=work_data["title"],
        body=work_data.get("body", ""),
        state=work_data.get("state", "open"),
        author_id=work_data.get("author_id"),
        labels=tuple(work_data.get("labels", [])),
    )
    task = DeliveryTask(
        repository=repository,
        work_item=work_item,
        target_branch=task_data["target_branch"],
        metadata=task_data.get("metadata", {}),
    )

    execution_data = payload.get("execution")
    execution = (
        ExecutionResult(**execution_data)
        if execution_data is not None
        else None
    )

    cr_data = payload.get("change_request")
    change_request = (
        ChangeRequestRef(repository=repository, **cr_data)
        if cr_data is not None
        else None
    )

    run_data = payload.get("ci_run")
    ci_run = (
        CIRunRef(repository=repository, **run_data)
        if run_data is not None
        else None
    )

    ci_logs = tuple(
        CIJobLog(run=ci_run, **item)
        for item in payload.get("ci_logs", [])
        if ci_run is not None
    )

    verification_data = payload.get("verification")
    verification = (
        VerificationResult(
            accepted=verification_data["accepted"],
            summary=verification_data["summary"],
            evidence=tuple(verification_data.get("evidence", [])),
        )
        if verification_data is not None
        else None
    )

    return DeliveryState(
        task=task,
        phase=DeliveryPhase(payload["phase"]),
        execution=execution,
        change_request=change_request,
        ci_run=ci_run,
        ci_logs=ci_logs,
        verification=verification,
    )
