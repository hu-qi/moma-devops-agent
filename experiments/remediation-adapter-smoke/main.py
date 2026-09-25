"""Smoke coverage for same-branch remediation adapters."""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from devopspilot.adapters.git.existing_branch import GitExistingBranchWorkspaceProvider
from devopspilot.adapters.github.client import GitHubHTTPClient
from devopspilot.adapters.openjiuwen.remediation import OpenJiuwenRemediationExecutor
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import CIRunRef, RepositoryRef, WorkItemRef
from devopspilot.contracts.remediation import CIFailureAnalysis, CIFailureKind


def git(cwd: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


class CapturingExecutor:
    def __init__(self) -> None:
        self.task = None

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        self.task = task
        return ExecutionResult(
            source_branch=task.metadata["source_branch"],
            commit_sha="repair-commit",
            summary="repair",
            published=True,
            test_summary="verification passed",
        )


async def workspace_contract() -> None:
    with tempfile.TemporaryDirectory() as tmp_value:
        tmp = Path(tmp_value)
        remote = tmp / "remote.git"
        repo = tmp / "repo"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True)
        subprocess.run(["git", "init", str(repo)], check=True)
        git(repo, "config", "user.name", "DevOpsPilot")
        git(repo, "config", "user.email", "devopspilot@local")
        (repo / "app.py").write_text("value = 'base'\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-m", "base")
        git(repo, "branch", "-M", "main")
        git(repo, "remote", "add", "origin", str(remote))
        git(repo, "push", "-u", "origin", "main")
        git(repo, "checkout", "-b", "devopspilot/live-fix")
        (repo / "app.py").write_text("value = 'candidate'\n", encoding="utf-8")
        git(repo, "add", "app.py")
        git(repo, "commit", "-m", "candidate")
        git(repo, "push", "origin", "devopspilot/live-fix")
        candidate_sha = git(repo, "rev-parse", "HEAD")
        git(repo, "checkout", "main")

        repository = RepositoryRef("git", "repo-1", "acme/demo", "main")
        work = WorkItemRef(repository, "7", "repair")
        task = DeliveryTask(
            repository,
            work,
            "main",
            metadata={
                "source_branch": "devopspilot/live-fix",
                "execution_id": "remediation-1",
            },
        )
        provider = GitExistingBranchWorkspaceProvider(repo)
        workspace = await provider.prepare(task)
        try:
            assert workspace.source_branch == "devopspilot/live-fix"
            assert workspace.base_commit == candidate_sha
            assert git(workspace.path, "rev-parse", "HEAD") == candidate_sha
            assert workspace.metadata["local_execution_branch"].startswith(
                "devopspilot-local/"
            )
        finally:
            await provider.cleanup(workspace)


async def remediation_contract() -> None:
    repository = RepositoryRef("github", "repo-1", "acme/demo", "main")
    work = WorkItemRef(repository, "7", "repair", "Original issue body")
    task = DeliveryTask(
        repository,
        work,
        "main",
        metadata={
            "allowed_paths": "app.py",
            "test_command": "python test_app.py",
        },
    )
    run = CIRunRef(
        "github-actions",
        "100",
        repository,
        "completed",
        "failure",
        "bad-commit",
    )
    state = DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=ExecutionResult(
            "devopspilot/live-fix",
            "bad-commit",
            "candidate",
            True,
        ),
        ci_run=run,
    )
    inner = CapturingExecutor()
    adapter = OpenJiuwenRemediationExecutor(inner)
    result = await adapter.remediate(
        state,
        CIFailureAnalysis(
            CIFailureKind.CODE,
            "tests failed",
            ("pytest: AssertionError: expected fixed",),
        ),
        attempt=1,
    )
    assert result.source_branch == "devopspilot/live-fix"
    assert inner.task.metadata["source_branch"] == "devopspilot/live-fix"
    assert inner.task.metadata["execution_id"] == "remediation-1"
    assert "AssertionError: expected fixed" in inner.task.work_item.body
    assert inner.task.metadata["allowed_paths"] == "app.py"




async def cross_origin_log_redirect_contract() -> None:
    storage_headers: dict[str, str | None] = {}

    class StorageHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            storage_headers["authorization"] = self.headers.get("Authorization")
            if storage_headers["authorization"]:
                self.send_response(401)
                self.end_headers()
                return
            payload = b"fixture log payload"
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args) -> None:
            return None

    storage = ThreadingHTTPServer(("127.0.0.1", 0), StorageHandler)
    storage_port = storage.server_address[1]

    class GitHubHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            assert self.headers.get("Authorization") == "Bearer test-token"
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{storage_port}/signed-log",
            )
            self.end_headers()

        def log_message(self, *_args) -> None:
            return None

    github = ThreadingHTTPServer(("127.0.0.1", 0), GitHubHandler)
    github_port = github.server_address[1]
    threads = [
        threading.Thread(target=storage.serve_forever, daemon=True),
        threading.Thread(target=github.serve_forever, daemon=True),
    ]
    for thread in threads:
        thread.start()

    try:
        client = GitHubHTTPClient(
            token="test-token",
            api_base=f"http://127.0.0.1:{github_port}",
        )
        payload = await client.request_bytes("GET", "/logs")
        assert payload == b"fixture log payload"
        assert storage_headers["authorization"] is None
    finally:
        github.shutdown()
        storage.shutdown()
        github.server_close()
        storage.server_close()


async def safe_shutdown_contract() -> None:
    from unittest.mock import MagicMock, patch
    from devopspilot.adapters.openjiuwen.executor import (
        _safe_runner_stop,
        _safe_capture_drain,
        _safe_capture_close,
        _patch_openjiuwen_lock_manager,
    )

    class DummyLockManager:
        _cleanup_task = None
        _locks = {"key": "val"}
        _idle_heap = [1]
        _idle_deadlines = {"k": 1.0}
        _state_lock = object()

        @classmethod
        def lock_guard(cls, *args, **kwargs):
            raise RuntimeError("should be patched")

    class DummyFsOperation:
        @classmethod
        def _file_lock(cls, *args, **kwargs):
            raise RuntimeError("should be patched")

    with patch.dict(
        "sys.modules",
        {
            "openjiuwen.core.sys_operation.local._rw_lock_manager": MagicMock(
                ReadWriteLockManager=DummyLockManager
            ),
            "openjiuwen.core.sys_operation.local.fs_operation": MagicMock(
                FsOperation=DummyFsOperation
            ),
        },
    ):
        _patch_openjiuwen_lock_manager()
        assert DummyLockManager._locks == {}
        assert DummyLockManager._idle_heap == []
        assert DummyLockManager._idle_deadlines == {}
        assert DummyLockManager._state_lock is None

        # Verify lock_guard and _file_lock are no-ops
        async def check_noop() -> None:
            async with DummyLockManager.lock_guard("path", "read", 1.0):
                pass
            async with DummyFsOperation._file_lock("path", "read", 1.0):
                pass

        asyncio.run(check_noop()) if not asyncio.get_event_loop().is_running() else await check_noop()

    hang_event = asyncio.Event()
    dummy_runner = MagicMock()
    dummy_runner.stop = hang_event.wait
    with patch.dict(
        "sys.modules",
        {"openjiuwen.core.runner.runner": MagicMock(Runner=dummy_runner)},
    ):
        start = asyncio.get_running_loop().time()
        await _safe_runner_stop(timeout=0.1)
        elapsed = asyncio.get_running_loop().time() - start
        assert elapsed < 1.0, f"Expected fast timeout return, took {elapsed}s"

    broken_capture = MagicMock()
    broken_capture.drain.side_effect = RuntimeError("drain failed")
    broken_capture.close.side_effect = RuntimeError("close failed")
    assert _safe_capture_drain(broken_capture) is None
    _safe_capture_close(broken_capture)


async def main() -> None:
    await workspace_contract()
    await remediation_contract()
    await cross_origin_log_redirect_contract()
    await safe_shutdown_contract()
    print("REMEDIATION_EXISTING_BRANCH_WORKSPACE_OK")
    print("REMEDIATION_AGENT_CONTEXT_OK")
    print("REMEDIATION_SOURCE_BRANCH_IDENTITY_OK")
    print("GITHUB_CROSS_ORIGIN_LOG_REDIRECT_OK")
    print("OPENJIUWEN_SAFE_SHUTDOWN_OK")


if __name__ == "__main__":
    asyncio.run(main())
