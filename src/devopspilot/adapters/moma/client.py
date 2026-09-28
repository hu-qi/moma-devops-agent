"""Direct HTTP client for MoMA MaaS inference API (OpenAI compatible)."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from typing import Any, Mapping


class MoMAClient:
    """Lightweight zero-dependency HTTP client for MoMA inference platform."""

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = (api_key or os.environ.get("MOMA_API_KEY", "")).strip()
        base = (api_base or os.environ.get("MOMA_API_BASE", "")).strip().rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        self.api_base = base
        self.default_model = (default_model or os.environ.get("MOMA_MODEL", "deepseek-v4.1-flash")).strip()
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("MOMA_API_KEY is required for MoMAClient")

    def chat_completion(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base}/chat/completions"
        chosen_model = model or self.default_model
        payload: dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "DevOpsPilot-MoMA-Client/0.1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"MoMA API Error (HTTP {exc.code}): {err_body}") from exc
        except Exception as exc:
            raise RuntimeError(f"MoMA network request failed: {exc}") from exc
