"""SQLite DeliveryState persistence smoke."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.state import DeliveryStateConflict
from devopspilot.persistence import SQLiteDeliveryStateStore


async def main() -> None:
    db = Path(tempfile.mkdtemp()) / "delivery.db"
    store = SQLiteDeliveryStateStore(db)

    repo = RepositoryRef(
        provider_id="github",
        repository_id="42",
        full_name="acme/demo",
        default_branch="main",
    )
    task = DeliveryTask(
        repository=repo,
        work_item=WorkItemRef(
            repository=repo,
            item_id="7",
            title="Fix CI",
            labels=("bug", "ci"),
        ),
        target_branch="main",
    )
    execution = ExecutionResult(
        source_branch="devopspilot/fix-7",
        commit_sha="deadbeef",
        summary="fixed",
        published=True,
    )
    change = ChangeRequestRef(
        repository=repo,
        change_id="9",
        title="Fix CI",
        source_branch=execution.source_branch,
        target_branch="main",
        state="open",
    )
    run = CIRunRef(
        provider_id="github-actions",
        run_id="100",
        repository=repo,
        status="completed",
        conclusion="failure",
        commit_sha="deadbeef",
    )
    state = DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=execution,
        change_request=change,
        ci_run=run,
        ci_logs=(CIJobLog(run, "201", "test", "pytest failed"),),
    )

    first = await store.save("delivery-7", state, expected_version=0)
    assert first.version == 1

    loaded = await store.load("delivery-7")
    assert loaded is not None
    assert loaded.version == 1
    assert loaded.state.phase is DeliveryPhase.CI_FAILED
    assert loaded.state.ci_logs[0].content == "pytest failed"
    assert loaded.state.task.work_item.labels == ("bug", "ci")

    second = await store.save(
        "delivery-7",
        loaded.state,
        expected_version=loaded.version,
    )
    assert second.version == 2

    try:
        await store.save(
            "delivery-7",
            loaded.state,
            expected_version=1,
        )
    except DeliveryStateConflict:
        pass
    else:
        raise AssertionError("stale delivery version must be rejected")

    reopened = SQLiteDeliveryStateStore(db)
    persisted = await reopened.load("delivery-7")
    assert persisted is not None and persisted.version == 2

    print("DELIVERY_STATE_SQLITE_OK")
    print("DELIVERY_STATE_RESTART_RECOVERY_OK")
    print("DELIVERY_STATE_OPTIMISTIC_LOCK_OK")


if __name__ == "__main__":
    asyncio.run(main())
