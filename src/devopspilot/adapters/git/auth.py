"""Credential-safe git clone helpers (C06).

Tokens must never be embedded in clone URLs: they leak into `git remote -v`,
error messages, logs and persisted state. Instead, authentication is injected
as a per-invocation `http.extraHeader` git config, which is never persisted.
"""

from __future__ import annotations

import base64
import re


def build_clone_auth_args(provider: str, token: str) -> list[str]:
    """Return git `-c` args carrying auth via HTTP header for the given provider.

    Empty/whitespace token => no auth args (public repo access).
    """
    token = (token or "").strip()
    if not token:
        return []

    if provider == "github":
        raw = f"x-access-token:{token}".encode("utf-8")
    else:  # atomgit (and default) use oauth2 basic scheme
        raw = f"oauth2:{token}".encode("utf-8")

    b64 = base64.b64encode(raw).decode("ascii")
    return [
        "-c",
        f"http.https://*.extraheader=AUTHORIZATION: basic {b64}",
    ]


_TOKEN_URL_RE = re.compile(r"(https?://)([^/@\s:]+):([^@\s/]+)@")


def sanitize_error(message: str) -> str:
    """Mask credentials embedded in URLs inside error messages/logs (C06)."""
    if not message:
        return message
    return _TOKEN_URL_RE.sub(r"\1***:***@", message)
