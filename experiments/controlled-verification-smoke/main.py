"""Smoke test for controlled verification commands, timeouts, process group cleanup, and oracle tamper detection."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.orchestration.test_runner import (
    EmptyVerificationCommandError,
    OracleTamperError,
    VerificationTimeoutError,
    run_controlled_command,
    verify_oracle_not_tampered,
)


def test_empty_verification_command_error() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_cmd_test_"))
    try:
        # If require_non_empty is False -> returns empty result
        res = asyncio.run(run_controlled_command("", cwd=tmp, require_non_empty=False))
        assert res.returncode == 0

        # If require_non_empty is True -> raises EmptyVerificationCommandError
        try:
            asyncio.run(run_controlled_command("   ", cwd=tmp, require_non_empty=True))
            assert False, "Should have raised EmptyVerificationCommandError"
        except EmptyVerificationCommandError as exc:
            assert "command is empty" in str(exc)
        print("CONTROLLED_CMD_EMPTY_CHECK_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_timeout_and_process_cleanup() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_cmd_test_"))
    try:
        # Command that sleeps longer than timeout
        cmd = f"{sys.executable} -c 'import time; time.sleep(10)'"
        try:
            asyncio.run(run_controlled_command(cmd, cwd=tmp, timeout_seconds=0.5))
            assert False, "Should have raised VerificationTimeoutError"
        except VerificationTimeoutError as exc:
            assert "timed out after 0.5s" in str(exc)
        print("CONTROLLED_CMD_TIMEOUT_AND_CLEANUP_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_oracle_tamper_detection() -> None:
    tmp_repo = Path(tempfile.mkdtemp(prefix="devopspilot_oracle_repo_"))
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "DevOpsPilot"], cwd=tmp_repo, check=True)
        subprocess.run(["git", "config", "user.email", "devopspilot@local"], cwd=tmp_repo, check=True)

        app_file = tmp_repo / "app.py"
        app_file.write_text("def run(): pass\n", encoding="utf-8")
        test_file = tmp_repo / "test_app.py"
        test_file.write_text("def test_run(): assert True\n", encoding="utf-8")

        subprocess.run(["git", "add", "."], cwd=tmp_repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_repo, check=True, capture_output=True)

        forbidden = ("test_app.py",)

        # 1. Untouched oracle -> passes
        verify_oracle_not_tampered(tmp_repo, forbidden)

        # 2. Tampered oracle -> raises OracleTamperError
        test_file.write_text("def test_run(): pass\n", encoding="utf-8")
        try:
            verify_oracle_not_tampered(tmp_repo, forbidden)
            assert False, "Should have raised OracleTamperError"
        except OracleTamperError as exc:
            assert "modified forbidden oracle test file 'test_app.py'" in str(exc)
        print("ORACLE_TAMPER_DETECTION_OK")
    finally:
        shutil.rmtree(tmp_repo, ignore_errors=True)


def main() -> None:
    test_empty_verification_command_error()
    test_timeout_and_process_cleanup()
    test_oracle_tamper_detection()
    print("ALL CONTROLLED VERIFICATION SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
