"""Controlled runner for Industry Engineering Pack test gates with process isolation and timeout cleanup."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from devopspilot.contracts.industry import (
    GateExecutionResult,
    IndustryEngineeringPack,
    IndustryGateBlockedError,
)
from devopspilot.orchestration.test_runner import (
    VerificationError,
    VerificationTimeoutError,
    run_controlled_command,
)


class IndustryGateRunner:
    """Executes domain-specific test gates with strict timeouts and failure enforcement."""

    def __init__(self, default_timeout_seconds: float = 60.0) -> None:
        self._default_timeout = default_timeout_seconds

    async def run_gates(
        self,
        pack: IndustryEngineeringPack,
        cwd: Path,
        *,
        enforce_required: bool = True,
    ) -> tuple[GateExecutionResult, ...]:
        results: list[GateExecutionResult] = []

        for gate in pack.test_gates:
            timeout_sec = float(gate.timeout_seconds or self._default_timeout)
            try:
                run_res = await run_controlled_command(
                    gate.command,
                    cwd=cwd,
                    timeout_seconds=timeout_sec,
                    require_non_empty=True,
                )
                passed = (run_res.returncode == 0)
                results.append(
                    GateExecutionResult(
                        gate_id=gate.gate_id,
                        name=gate.name,
                        required=gate.required,
                        passed=passed,
                        returncode=run_res.returncode,
                        stdout=run_res.stdout,
                        stderr=run_res.stderr,
                        timed_out=False,
                        message="" if passed else f"Gate command exited with returncode {run_res.returncode}",
                    )
                )
            except VerificationTimeoutError as exc:
                results.append(
                    GateExecutionResult(
                        gate_id=gate.gate_id,
                        name=gate.name,
                        required=gate.required,
                        passed=False,
                        returncode=124,
                        timed_out=True,
                        message=f"Gate timed out after {timeout_sec}s: {exc}",
                    )
                )
            except VerificationError as exc:
                results.append(
                    GateExecutionResult(
                        gate_id=gate.gate_id,
                        name=gate.name,
                        required=gate.required,
                        passed=False,
                        returncode=1,
                        timed_out=False,
                        message=str(exc),
                    )
                )

        if enforce_required:
            failed_required = [r for r in results if r.required and not r.passed]
            if failed_required:
                first = failed_required[0]
                raise IndustryGateBlockedError(
                    f"Required industry gate '{first.name}' ({first.gate_id}) failed: {first.message or first.stderr}"
                )

        return tuple(results)
