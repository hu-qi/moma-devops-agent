"""Web console behavior uses the canonical delivery store, never demo rows."""

import asyncio
import json
import sqlite3

import pytest

from devopspilot.contracts.delivery import DeliveryPhase, DeliveryState, DeliveryTask
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore
from devopspilot.web.console import ConsoleService, sanitize


def save_state(path, phase=DeliveryPhase.CI_PENDING):
    repo = RepositoryRef(
        provider_id="github", repository_id="org/repo", full_name="org/repo"
    )
    task = DeliveryTask(
        repo, WorkItemRef(repo, "42", "真实任务", author_id="alice"), "main"
    )
    store = SQLiteDeliveryStateStore(path)
    asyncio.run(
        store.save("delivery-42", DeliveryState(task, phase), expected_version=0)
    )


def test_reads_canonical_payload_and_pending_is_not_complete(tmp_path):
    path = tmp_path / "state.db"
    save_state(path)
    service = ConsoleService(path)
    item = service.deliveries()["items"][0]
    assert (item["title"], item["repository"], item["phase"], item["completed"]) == (
        "真实任务",
        "org/repo",
        "ci-pending",
        False,
    )


def test_missing_database_is_empty_not_seeded(tmp_path):
    service = ConsoleService(tmp_path / "state.db")
    assert service.deliveries()["items"] == []


def test_secrets_removed_from_nested_text(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-private-token-value")
    assert "test-private-token-value" not in json.dumps(
        sanitize({"note": "error test-private-token-value", "token": "x"})
    )


def test_live_submit_missing_configuration_has_no_job(tmp_path, monkeypatch):
    monkeypatch.delenv("MOMA_API_KEY", raising=False)
    service = ConsoleService(tmp_path / "state.db")
    with pytest.raises(ValueError, match="MOMA_API_KEY"):
        service.submit({"repo": "org/repo", "issue": "42", "provider": "github"})
    assert service.jobs() == []


def test_corrupt_database_is_error_not_empty_success(tmp_path):
    path = tmp_path / "broken.db"
    path.write_text("bad database")
    with pytest.raises(sqlite3.DatabaseError):
        ConsoleService(path).deliveries()


def test_rejected_pipeline_does_not_mark_later_stages_complete(tmp_path):
    path = tmp_path / "state.db"
    save_state(path, DeliveryPhase.REJECTED)
    item = ConsoleService(path).detail("delivery-42")
    assert item["stages"][-1]["status"] != "complete"


def test_no_active_rc_is_truthful(monkeypatch):
    from devopspilot.web import api

    class Result:
        returncode = 0
        stdout = ""

    monkeypatch.setattr(api.subprocess, "run", lambda *a, **k: Result())
    assert api._get_active_rc_tag() == "unreleased"


def test_duplicate_active_task_has_one_worker(tmp_path, monkeypatch):
    from devopspilot.web import console

    monkeypatch.setenv("MOMA_API_KEY", "fake-test-moma-key")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-test-github-token")
    starts = []

    class FakeThread:
        def __init__(self, **kwargs):
            starts.append(kwargs)

        def start(self):
            pass

    monkeypatch.setattr(console.threading, "Thread", FakeThread)
    service = ConsoleService(tmp_path / "state.db")
    body = {"provider": "github", "repo": "org/repo", "issue": "42"}
    first, second = service.submit(body), service.submit(body)
    assert first["job_id"] == second["job_id"] and len(starts) == 1


def test_restart_marks_running_job_interrupted_without_replay(tmp_path, monkeypatch):
    service = ConsoleService(tmp_path / "state.db")
    with service.connect() as db:
        db.execute(
            "INSERT INTO jobs VALUES ('j','github:org/repo','42','running',1,1,'{}')"
        )
    service.start()
    service.close()
    assert service.jobs()[0]["state"] == "interrupted"


def test_schedule_requires_future_time(tmp_path):
    service = ConsoleService(tmp_path / "state.db")
    with pytest.raises(ValueError, match="未来"):
        service.save_schedule(
            {"provider": "github", "repo": "org/repo", "issue": "42", "due": 1}
        )
    assert service.schedules() == []


def test_completed_phase_without_acceptance_is_not_verified(tmp_path):
    path = tmp_path / "state.db"
    save_state(path, DeliveryPhase.VERIFIED)
    assert ConsoleService(path).deliveries()["items"][0]["completed"] is False


def test_strict_live_atomgit_failure_never_creates_placeholder(tmp_path, monkeypatch):
    from devopspilot.cli.main import build_parser, run_cli
    from devopspilot.adapters.atomgit.scm import AtomGitSCMProvider

    monkeypatch.setenv("MOMA_API_KEY", "fake-test-moma-key")
    monkeypatch.setenv("ATOMGIT_TOKEN", "fake-test-atomgit-token")

    async def fail(*args, **kwargs):
        raise RuntimeError("API unavailable")

    monkeypatch.setattr(AtomGitSCMProvider, "get_repository", fail)
    db = tmp_path / "state.db"
    args = build_parser().parse_args(
        [
            "start",
            "--provider",
            "atomgit",
            "--repo",
            "org/repo",
            "--issue",
            "42",
            "--require-live",
            "--db",
            str(db),
        ]
    )
    assert asyncio.run(run_cli(args)) == 1
    assert ConsoleService(db).deliveries()["total"] == 0


def test_token_usage_metrics_are_not_credentials():
    assert sanitize(
        {"prompt_tokens": 123, "total_tokens": 456, "api_key": "secret"}
    ) == {"prompt_tokens": 123, "total_tokens": 456, "api_key": "[REDACTED]"}


def test_project_config_preserves_synced_issues(tmp_path):
    service = ConsoleService(tmp_path / "state.db")
    service.add_project({"provider": "github", "repo": "org/repo"})
    with service.connect() as db:
        data = json.loads(db.execute("SELECT payload FROM projects").fetchone()[0])
        data["issues"] = [{"id": "42"}]
        db.execute("UPDATE projects SET payload=?", (json.dumps(data),))
    result = service.add_project(
        {"provider": "github", "repo": "org/repo", "test_command": "python test_app.py"}
    )
    assert (
        result["issues"] == [{"id": "42"}]
        and result["trusted_config"]["test_command"] == "python test_app.py"
    )


def test_verification_degradation_survives_persistence(tmp_path):
    from devopspilot.contracts.delivery import VerificationResult

    path = tmp_path / "state.db"
    repo = RepositoryRef(
        provider_id="github", repository_id="org/repo", full_name="org/repo"
    )
    state = DeliveryState(
        DeliveryTask(repo, WorkItemRef(repo, "42", "degraded"), "main"),
        DeliveryPhase.VERIFIED,
        verification=VerificationResult(
            accepted=True,
            summary="degraded",
            runtime_clean_completion=False,
            degradation_reason="runtime timeout",
            outcome_status="verified_degraded",
        ),
    )
    store = SQLiteDeliveryStateStore(path)
    asyncio.run(store.save("degraded", state, expected_version=0))
    loaded = asyncio.run(store.load("degraded"))
    assert loaded.state.verification.runtime_clean_completion is False
    assert ConsoleService(path).deliveries()["items"][0]["completed"] is False


def test_cancel_stops_local_worker_process_group(tmp_path):
    import os
    import subprocess
    import sys

    service = ConsoleService(tmp_path / "state.db")
    with subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        start_new_session=os.name == "posix",
    ) as proc:
        service._processes["test-job"] = proc
        result = service.cancel_job({"job_id": "test-job"})
        assert result["state"] == "cancelled" and proc.wait(timeout=3) != 0


def test_cancel_unknown_job_does_not_claim_success(tmp_path):
    with pytest.raises(ValueError, match="未在当前服务"):
        ConsoleService(tmp_path / "state.db").cancel_job({"job_id": "unknown"})
