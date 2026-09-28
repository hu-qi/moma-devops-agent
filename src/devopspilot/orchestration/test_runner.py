"""Controlled verification command execution with timeouts, cancellation, and process group cleanup."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from dataclasses import dataclass
from pathlib import Path


class VerificationError(RuntimeError):
    """Base error for verification failures."""


class EmptyVerificationCommandError(VerificationError):
    """Raised when verification is required but command is empty."""


class VerificationTimeoutError(VerificationError):
    """Raised when verification command exceeds timeout."""


class OracleTamperError(VerificationError):
    """Raised when forbidden oracle / test files are modified."""


@dataclass(frozen=True, slots=True)
class ControlledRunResult:
    returncode: int
    stdout: str
    stderr: str
    combined_output: str
    timed_out: bool = False


async def run_controlled_command(
    command: str,
    *,
    cwd: Path,
    timeout_seconds: float = 60.0,
    require_non_empty: bool = False,
    env: dict[str, str] | None = None,
) -> ControlledRunResult:
    """Run a shell command with strict timeout and process group cleanup.

    - If require_non_empty is True and command is empty -> EmptyVerificationCommandError.
    - If command hangs beyond timeout_seconds -> process and child subprocesses killed, raises VerificationTimeoutError.
    """
    cleaned = command.strip()
    if not cleaned:
        if require_non_empty:
            raise EmptyVerificationCommandError(
                "Verification is required but verification command is empty"
            )
        return ControlledRunResult(
            returncode=0,
            stdout="",
            stderr="",
            combined_output="",
        )

    # Use start_new_session to place the subprocess in its own process group
    proc = await asyncio.create_subprocess_shell(
        cleaned,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        start_new_session=True,
    )

    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout_seconds,
        )
        stdout = stdout_b.decode("utf-8", errors="replace")
        stderr = stderr_b.decode("utf-8", errors="replace")
        combined = (stdout + "\n" + stderr).strip()[-4000:]
        return ControlledRunResult(
            returncode=proc.returncode if proc.returncode is not None else 1,
            stdout=stdout,
            stderr=stderr,
            combined_output=combined,
            timed_out=False,
        )
    except asyncio.TimeoutError:
        # Kill the entire process group
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except Exception:
            pass
        raise VerificationTimeoutError(
            f"Verification command timed out after {timeout_seconds}s and was terminated: {command[:80]}"
        )


def verify_oracle_not_tampered(
    workspace_path: Path,
    forbidden_paths: tuple[str, ...],
) -> None:
    """Ensure forbidden oracle test files are neither modified nor deleted."""
    import subprocess
    diff_proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "."],
        cwd=str(workspace_path),
        capture_output=True,
        text=True,
    )
    changed = set(line.strip() for line in diff_proc.stdout.splitlines() if line.strip())
    for forbidden in forbidden_paths:
        if forbidden in changed:
            raise OracleTamperError(
                f"Security violation: Agent modified forbidden oracle test file '{forbidden}'"
            )
