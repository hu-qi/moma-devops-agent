"""Minimal GitHub REST client boundary.

The provider adapters depend on this protocol rather than directly on a
specific HTTP library. This keeps mapping logic easy to contract-test.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener




class _CrossOriginSafeRedirectHandler(HTTPRedirectHandler):
    """Drop GitHub credentials when a download redirects off-origin.

    GitHub Actions log/artifact endpoints return a temporary redirect to a
    signed object-storage URL. Forwarding the GitHub Authorization header to
    that storage host can invalidate the signed request and leaks a credential
    to a different origin.
    """

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        redirected = super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl,
        )
        if redirected is None:
            return None
        if urlparse(req.full_url).netloc != urlparse(newurl).netloc:
            redirected.remove_header("Authorization")
            redirected.remove_header("X-GitHub-Api-Version")
        return redirected


class GitHubAPIError(RuntimeError):
    def __init__(self, status: int, message: str, *, path: str) -> None:
        super().__init__(f"GitHub API {status} for {path}: {message}")
        self.status = status
        self.path = path


class GitHubAPIClient(Protocol):
    async def request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
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
class GitHubHTTPClient:
    """Small stdlib-based client suitable for the first reference adapter.

    Secrets are supplied at runtime and are never persisted by this class.
    """

    token: str
    api_base: str = "https://api.github.com"
    api_version: str = "2022-11-28"
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
            clean_query = {k: v for k, v in query.items() if v is not None}
            if clean_query:
                url += "?" + urlencode(clean_query, doseq=True)

        data = None if body is None else json.dumps(body).encode("utf-8")
        request = Request(
            url,
            data=data,
            method=method.upper(),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": self.api_version,
                "User-Agent": self.user_agent,
                **({"Content-Type": "application/json"} if data is not None else {}),
            },
        )

        try:
            opener = build_opener(_CrossOriginSafeRedirectHandler())
            with opener.open(request, timeout=60) as response:  # noqa: S310
                return response.read()
        except HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            try:
                message = json.loads(payload).get("message", payload)
            except json.JSONDecodeError:
                message = payload
            raise GitHubAPIError(exc.code, str(message), path=path) from exc

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        raw = await asyncio.to_thread(
            self._request,
            method,
            path,
            body=body,
            query=query,
        )
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> bytes:
        return await asyncio.to_thread(self._request, method, path, query=query)
