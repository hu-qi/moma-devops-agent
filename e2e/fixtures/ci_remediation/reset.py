"""Idempotently restore the CI-remediation fixture to its broken baseline."""

from __future__ import annotations

import argparse
from pathlib import Path

BROKEN_SOURCE = '''def status() -> str:\n    """Return the current remediation fixture status."""\n    return "broken"\n'''


def reset_fixture(root: Path) -> bool:
    root.mkdir(parents=True, exist_ok=True)
    app = root / "app.py"
    before = app.read_text(encoding="utf-8") if app.exists() else ""
    app.write_text(BROKEN_SOURCE, encoding="utf-8")
    return before != BROKEN_SOURCE


def is_reset(root: Path) -> bool:
    app = root / "app.py"
    return app.exists() and app.read_text(encoding="utf-8") == BROKEN_SOURCE


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check:
        if not is_reset(root):
            raise SystemExit("fixture is not reset")
        print("CI_REMEDIATION_FIXTURE_RESET_OK")
        return
    changed = reset_fixture(root)
    assert is_reset(root)
    print("CI_REMEDIATION_FIXTURE_RESET_OK")
    print(f"changed={'true' if changed else 'false'}")


if __name__ == "__main__":
    main()
