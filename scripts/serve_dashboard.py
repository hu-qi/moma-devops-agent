#!/usr/bin/env python3
"""Launch the DevOpsPilot Management Console Web Dashboard."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure src/ is on sys.path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from devopspilot.web.server import run_dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DevOpsPilot Web Management Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("--db", default=None, help="Custom path to state SQLite database")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else None
    run_dashboard(host=args.host, port=args.port, db_path=db_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
