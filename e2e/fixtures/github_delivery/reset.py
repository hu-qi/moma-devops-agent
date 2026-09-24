"""Reset the GitHub delivery fixture to its deterministic broken state."""

from __future__ import annotations

from pathlib import Path


FIXTURE_DIR = Path(__file__).resolve().parent
APP = FIXTURE_DIR / "app.py"
BROKEN_APP = '''def status() -> str:
    """Return the current fixture status."""
    return "broken"
'''


def reset() -> None:
    """Idempotently restore the exact broken fixture used by delivery E2E."""
    APP.write_text(BROKEN_APP, encoding="utf-8")


if __name__ == "__main__":
    reset()
    print("GITHUB_DELIVERY_FIXTURE_RESET_OK")
