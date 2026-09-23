"""Transport wrapper around the official CNB OpenAPI CLI.

This module intentionally contains no SCM/CI domain mapping yet. The command
surface and response shapes must be verified before implementing providers.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class CNBCLIError(RuntimeError):
    def __init__(self, args: Sequence[str], returncode: int, stderr: str) -> None:
        safe_command = " ".join(args)
        super().__init__(f"CNB CLI failed ({returncode}): {safe_command}: {stderr.strip()}")
        self.returncode = returncode
        self.stderr = stderr


@dataclass(slots=True)
class CNBCLIClient:
    token: str | None = None
    api_endpoint: str = "https://api.cnb.cool"
    binary: str = "cnb"

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["CNB_API_ENDPOINT"] = self.api_endpoint
        if self.token:
            env["CNB_TOKEN"] = self.token
        return env

    async def run_text(self, *args: str) -> str:
        command = (self.binary, *args)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self._env(),
        )
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode("utf-8", errors="replace")
        stderr_text = stderr.decode("utf-8", errors="replace")
        if process.returncode != 0:
            raise CNBCLIError(command, process.returncode or 1, stderr_text)
        return stdout_text

    async def run_json(self, *args: str) -> Any:
        output = await self.run_text(*args)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise CNBCLIError(
                (self.binary, *args),
                0,
                "CNB CLI output was not valid JSON; response format must be verified",
            ) from exc

    async def probe(self) -> Mapping[str, str]:
        return {
            "version": (await self.run_text("--version")).strip(),
            "api_endpoint": self.api_endpoint,
        }
