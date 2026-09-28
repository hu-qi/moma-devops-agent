"""Smoke test for unified DevOpsPilot CLI commands: start, status, resume, and report."""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# Offline guarantee (C01): strip live credentials BEFORE devopspilot imports,
# so the CLI start path never attempts real SCM/MoMA calls in this smoke test.
for _var in ("MOMA_API_KEY", "DEEPSEEK_API_KEY", "ATOMGIT_TOKEN", "GITHUB_TOKEN", "CNB_TOKEN"):
    os.environ.pop(_var, None)
# Prevent .env auto-loader from re-injecting credentials from the developer's working copy
os.environ["DEVOPSPILOT_NO_DOTENV"] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.cli.main import build_parser, main, run_cli
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.contracts.review import ReviewResult, ReviewVerdict
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore

REPO = RepositoryRef(provider_id="mock", repository_id="repo-cli", full_name="org/cli-repo", default_branch="main")


def test_cli_parser() -> None:
    parser = build_parser()

    # 1. Test start arguments
    args_start = parser.parse_args(["start", "--repo", "org/repo", "--issue", "123", "--mode", "single_agent"])
    assert args_start.command == "start"
    assert args_start.repo == "org/repo"
    assert args_start.issue == "123"
    assert args_start.mode == "single_agent"

    # 2. Test status arguments
    args_status = parser.parse_args(["status", "--delivery-id", "deliv-100", "--format", "json"])
    assert args_status.command == "status"
    assert args_status.delivery_id == "deliv-100"
    assert args_status.format == "json"

    # 3. Test report arguments
    args_report = parser.parse_args(["report", "--delivery-id", "deliv-100", "--format", "markdown"])
    assert args_report.command == "report"
    assert args_report.format == "markdown"
    print("CLI_PARSER_CONFIG_OK")


def test_cli_execution_with_storage() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_cli_test_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)

        # Seed a completed delivery in state
        task = DeliveryTask(repository=REPO, work_item=WorkItemRef(repository=REPO, item_id="42", title="test item"), target_branch="main")
        exec_res = ExecutionResult(
            source_branch="feat",
            commit_sha="c998877",
            summary="fixed",
            published=True,
            review=ReviewResult(
                reviewer_id="reviewer-01",
                verdict=ReviewVerdict.APPROVED,
                diff_digest="digest-abc",
                summary="approved",
            ),
        )
        state = DeliveryState(task=task, phase=DeliveryPhase.CHANGE_OPENED, execution=exec_res)
        import asyncio
        asyncio.run(store.save("deliv-cli-001", state, expected_version=0))

        # 1. Test status command
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main(["status", "--delivery-id", "deliv-cli-001", "--db", str(db_path), "--format", "json"])
        assert ret == 0
        output = buf.getvalue()
        assert "deliv-cli-001" in output
        assert "c998877" in output
        print("CLI_STATUS_COMMAND_OK")

        # 2. Test report command (markdown)
        buf_rep = io.StringIO()
        with redirect_stdout(buf_rep):
            ret_rep = main(["report", "--delivery-id", "deliv-cli-001", "--db", str(db_path), "--format", "markdown"])
        assert ret_rep == 0
        rep_out = buf_rep.getvalue()
        assert "# DevOpsPilot Delivery Report: deliv-cli-001" in rep_out
        assert "c998877" in rep_out
        assert "approved" in rep_out.lower()
        print("CLI_REPORT_COMMAND_OK")

        # 3. Test start command
        buf_start = io.StringIO()
        with redirect_stdout(buf_start):
            ret_start = main(["start", "--repo", "repo-1", "--issue", "55", "--db", str(db_path)])
        assert ret_start == 0
        assert "Delivery initialized:" in buf_start.getvalue()
        print("CLI_START_COMMAND_OK")

        # 4. Test error handling for non-existent delivery
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            ret_err = main(["status", "--delivery-id", "non-existent", "--db", str(db_path)])
        assert ret_err == 1
        assert "not found" in err_buf.getvalue().lower()
        print("CLI_ERROR_HANDLING_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main_test() -> None:
    test_cli_parser()
    test_cli_execution_with_storage()
    print("ALL CLI SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main_test()
