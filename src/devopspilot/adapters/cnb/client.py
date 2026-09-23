"""CNB transports: official CLI plus direct OpenAPI client."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class CNBAPIError(RuntimeError):
    def __init__(self, status: int, message: str, *, path: str) -> None:
        super().__init__(f"CNB API {status} for {path}: {message}")
        self.status = status
        self.path = path


class CNBAPIClient(Protocol):
    async def request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        ...


@dataclass(slots=True)
class CNBHTTPClient:
    token: str
    api_base: str = "https://api.cnb.cool"
    user_agent: str = "DevOpsPilot"

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> bytes:
        url = f"{self.api_base.rstrip('/')}/{path.lstrip('/')}"
        if query:
            clean = {k: v for k, v in query.items() if v is not None}
            if clean:
                url += "?" + urlencode(clean, doseq=True)
        data = None if body is None else json.dumps(body).encode()
        req = Request(
            url,
            data=data,
            method=method.upper(),
            headers={
                "Accept": "application/vnd.cnb.api+json",
                "Authorization": f"Bearer {self.token}",
                "User-Agent": self.user_agent,
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )
        try:
            with urlopen(req, timeout=60) as response:  # noqa: S310
                return response.read()
        except HTTPError as exc:
            raw = exc.read().decode(errors="replace")
            raise CNBAPIError(exc.code, raw, path=path) from exc

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        raw = await asyncio.to_thread(self._request, method, path, body=body, query=query)
        return None if not raw else json.loads(raw.decode())

    @staticmethod
    def repo_path(full_name: str) -> str:
        return quote(full_name, safe="/")


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
