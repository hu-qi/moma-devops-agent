"""Shared pytest fixtures: guarantee offline test runs by scrubbing live credentials.

Per IMPLEMENTATION_PLAN.md C01: test processes must clear live credentials so
no test can accidentally hit real SCM/MoMA services. Set DEVOPSPILOT_ALLOW_LIVE_CREDS=1
to explicitly opt out (not used by CI).
"""

import os
import sys
from pathlib import Path

import pytest

# Live credential env vars that must never leak into tests
_LIVE_CREDENTIAL_VARS = (
    "MOMA_API_KEY",
    "DEEPSEEK_API_KEY",
    "ATOMGIT_TOKEN",
    "GITHUB_TOKEN",
    "CNB_TOKEN",
)


def pytest_configure(config):
    """Scrub live credentials from the test process environment (C01)."""
    if os.environ.get("DEVOPSPILOT_ALLOW_LIVE_CREDS", "").strip() == "1":
        return
    for var in _LIVE_CREDENTIAL_VARS:
        os.environ.pop(var, None)
    # Also force offline branding so tests never depend on .env URLs
    os.environ.setdefault("PYTHONPATH", "src")


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """Per-test autouse fixture: double-guarantee no live credentials present."""
    if os.environ.get("DEVOPSPILOT_ALLOW_LIVE_CREDS", "").strip() == "1":
        yield
        return
    for var in _LIVE_CREDENTIAL_VARS:
        monkeypatch.delenv(var, raising=False)
    yield
