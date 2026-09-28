"""SQLite persistence for resumable DeliveryState."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
    VerificationResult,
)
from devopspilot.contracts.review import (
    ReviewFinding,
    ReviewResult,
    ReviewVerdict,
)
from devopspilot.contracts.industry import PackRef
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.state import (
    DeliveryStateConflict,
    IntentStatus,
    LeaseAcquireResult,
    LeaseAcquisitionError,
    StoredDeliveryState,
)


class SQLiteDeliveryStateStore:
    def __init__(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self._path = str(p)
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
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS delivery_intents (
                    deduplication_key TEXT PRIMARY KEY,
                    delivery_id TEXT NOT NULL,
                    lease_owner TEXT NOT NULL,
                    lease_token TEXT NOT NULL,
                    lease_expires_at REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )

    async def acquire_lease(
        self,
        deduplication_key: str,
        delivery_id: str,
        *,
        owner: str = "worker",
        ttl_seconds: float = 300.0,
    ) -> LeaseAcquireResult:
        return await asyncio.to_thread(
            self._acquire_lease_sync,
            deduplication_key,
            delivery_id,
            owner,
            ttl_seconds,
        )

    def _acquire_lease_sync(
        self,
        deduplication_key: str,
        delivery_id: str,
        owner: str,
        ttl_seconds: float,
    ) -> LeaseAcquireResult:
        now = time.time()
        token = uuid.uuid4().hex
        expires_at = now + ttl_seconds

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT delivery_id, lease_owner, lease_token, lease_expires_at, status "
                "FROM delivery_intents WHERE deduplication_key = ?",
                (deduplication_key,),
            ).fetchone()

            if row is None:
                db.execute(
                    "INSERT INTO delivery_intents("
                    "deduplication_key, delivery_id, lease_owner, lease_token, lease_expires_at, status, created_at, updated_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (deduplication_key, delivery_id, owner, token, expires_at, IntentStatus.ACQUIRED.value, now, now),
                )
                return LeaseAcquireResult(
                    acquired=True,
                    delivery_id=delivery_id,
                    lease_token=token,
                    status=IntentStatus.ACQUIRED,
                    message="Acquired new execution lease",
                )

            existing_delivery_id = row["delivery_id"]
            existing_owner = row["lease_owner"]
            existing_expires = float(row["lease_expires_at"])
            existing_status = row["status"]

            # Check if this task already has an existing delivery state
            existing_state_row = db.execute(
                "SELECT delivery_id, version, payload FROM delivery_state WHERE delivery_id = ?",
                (existing_delivery_id,),
            ).fetchone()
            existing_state = (
                StoredDeliveryState(
                    delivery_id=existing_state_row["delivery_id"],
                    version=int(existing_state_row["version"]),
                    state=_decode_state(json.loads(existing_state_row["payload"])),
                )
                if existing_state_row is not None
                else None
            )

            # If task already completed or already has a persisted delivery state
            if existing_status == IntentStatus.COMPLETED.value or (
                existing_state is not None and existing_state.state.phase not in {DeliveryPhase.RECEIVED}
            ):
                return LeaseAcquireResult(
                    acquired=False,
                    delivery_id=existing_delivery_id,
                    existing_state=existing_state,
                    status=IntentStatus.COMPLETED,
                    message=f"Task already executed with delivery_id={existing_delivery_id}",
                )

            # Check if lease expired (can be taken over)
            if now >= existing_expires and existing_status != IntentStatus.COMPLETED.value:
                db.execute(
                    "UPDATE delivery_intents SET "
                    "lease_owner = ?, lease_token = ?, lease_expires_at = ?, status = ?, updated_at = ? "
                    "WHERE deduplication_key = ?",
                    (owner, token, expires_at, IntentStatus.ACQUIRED.value, now, deduplication_key),
                )
                return LeaseAcquireResult(
                    acquired=True,
                    delivery_id=existing_delivery_id,
                    existing_state=existing_state,
                    lease_token=token,
                    status=IntentStatus.ACQUIRED,
                    message=f"Expired lease previously held by {existing_owner} taken over",
                )

            # Active lease held by someone else
            return LeaseAcquireResult(
                acquired=False,
                delivery_id=existing_delivery_id,
                existing_state=existing_state,
                status=IntentStatus.RUNNING,
                message=f"Active lease held by {existing_owner} until {existing_expires}",
            )

    async def release_lease(
        self,
        deduplication_key: str,
        lease_token: str,
    ) -> None:
        await asyncio.to_thread(self._release_lease_sync, deduplication_key, lease_token)

    def _release_lease_sync(self, deduplication_key: str, lease_token: str) -> None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE delivery_intents SET "
                "status = ?, updated_at = ? "
                "WHERE deduplication_key = ? AND lease_token = ? AND status != ?",
                (IntentStatus.FAILED.value, now, deduplication_key, lease_token, IntentStatus.COMPLETED.value),
            )

    async def complete_intent(
        self,
        deduplication_key: str,
        delivery_id: str,
    ) -> None:
        await asyncio.to_thread(self._complete_intent_sync, deduplication_key, delivery_id)

    def _complete_intent_sync(self, deduplication_key: str, delivery_id: str) -> None:
        now = time.time()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE delivery_intents SET "
                "status = ?, updated_at = ? "
                "WHERE deduplication_key = ? AND delivery_id = ?",
                (IntentStatus.COMPLETED.value, now, deduplication_key, delivery_id),
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
            "pack_ref": task.pack_ref.to_dict() if task.pack_ref else None,
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
            "review": (
                {
                    "reviewer_id": state.execution.review.reviewer_id,
                    "verdict": state.execution.review.verdict.value,
                    "diff_digest": state.execution.review.diff_digest,
                    "commit_sha": state.execution.review.commit_sha,
                    "summary": state.execution.review.summary,
                    "findings": [
                        {
                            "path": f.path,
                            "message": f.message,
                            "line": f.line,
                            "severity": f.severity,
                        }
                        for f in state.execution.review.findings
                    ],
                    "metadata": dict(state.execution.review.metadata),
                }
                if state.execution.review
                else None
            ),
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
    pack_ref_data = task_data.get("pack_ref")
    pack_ref = PackRef.from_dict(pack_ref_data) if pack_ref_data is not None else None
    task = DeliveryTask(
        repository=repository,
        work_item=work_item,
        target_branch=task_data["target_branch"],
        metadata=task_data.get("metadata", {}),
        pack_ref=pack_ref,
    )

    execution_data = payload.get("execution")
    if execution_data is not None:
        exec_kwargs = dict(execution_data)
        rev_data = exec_kwargs.get("review")
        review_obj = None
        if rev_data is not None:
            findings = tuple(
                ReviewFinding(**f) for f in rev_data.get("findings", [])
            )
            review_obj = ReviewResult(
                reviewer_id=rev_data["reviewer_id"],
                verdict=ReviewVerdict(rev_data["verdict"]),
                diff_digest=rev_data.get("diff_digest", ""),
                commit_sha=rev_data.get("commit_sha", ""),
                findings=findings,
                summary=rev_data.get("summary", ""),
                metadata=rev_data.get("metadata", {}),
            )
        exec_kwargs["review"] = review_obj
        execution = ExecutionResult(**exec_kwargs)
    else:
        execution = None

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
