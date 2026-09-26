"""AtomGit REST API client boundary.

Supports AtomGit OpenAPI endpoints under https://api.atomgit.com.
Follows the same lightweight Protocol abstraction as GitHub and CNB adapters.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, build_opener


class AtomGitAPIError(RuntimeError):
    def __init__(self, status: int, message: str, *, path: str) -> None:
        super().__init__(f"AtomGit API {status} for {path}: {message}")
        self.status = status
        self.path = path


class AtomGitAPIClient(Protocol):
    async def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        ...

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> bytes:
        ...


@dataclass(slots=True)
class AtomGitHTTPClient:
    token: str | None = None
    base_url: str = "https://api.atomgit.com"
    timeout_seconds: float = 30.0

    def _build_request(
        self,
        method: str,
        path: str,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> Request:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url = f"{url}?{urlencode(filtered)}"

        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "DevOpsPilot-AtomGitAdapter/0.1",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        return Request(url=url, data=data, headers=headers, method=method.upper())

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> Any:
        raw = await self.request_bytes(method, path, query=query, body=body)
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        body: Any = None,
    ) -> bytes:
        req = self._build_request(method, path, query, body)

        def _send() -> bytes:
            opener = build_opener()
            try:
                with opener.open(req, timeout=self.timeout_seconds) as resp:
                    return resp.read()
            except HTTPError as err:
                detail = err.read().decode("utf-8", errors="replace")
                raise AtomGitAPIError(err.code, detail, path=path) from err

        return await asyncio.to_thread(_send)
