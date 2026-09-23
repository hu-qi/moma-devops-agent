"""Minimal deterministic DevOpsBench runner.

V0.1 validates benchmark case metadata and the *seeded* fixture state.
Agent execution is intentionally not coupled to this runner yet.

For repair/debug cases, the fixture is expected to start broken:
- seed_expected_exit_code describes the expected initial state;
- expected_exit_code describes the target state after an Agent repair.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "cases"


def load_case(case_dir: Path) -> dict[str, Any]:
    with (case_dir / "case.json").open("r", encoding="utf-8") as f:
        case = json.load(f)

    required = {"id", "category", "task", "fixture", "oracle"}
    missing = sorted(required - set(case))
    if missing:
        raise ValueError(f"{case_dir.name}: missing fields: {', '.join(missing)}")
    return case


def run_seed_oracle(case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    fixture_src = case_dir / case["fixture"]["path"]
    if not fixture_src.exists():
        raise FileNotFoundError(f"fixture not found: {fixture_src}")

    oracle = case["oracle"]
    command = oracle.get("command")
    if not command:
        return {
            "case_id": case["id"],
            "category": case["category"],
            "phase": "seed-validation",
            "status": "metadata-only",
        }

    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="devopsbench-") as td:
        workspace = Path(td) / "workspace"
        shutil.copytree(fixture_src, workspace)
        completed = subprocess.run(
            command,
            cwd=workspace,
            shell=True,
            text=True,
            capture_output=True,
            timeout=int(case.get("budget", {}).get("timeout_seconds", 60)),
            check=False,
        )

    elapsed = time.perf_counter() - started
    seed_expected = int(
        oracle.get(
            "seed_expected_exit_code",
            oracle.get("expected_exit_code", 0),
        )
    )
    solution_expected = int(oracle.get("expected_exit_code", 0))

    return {
        "case_id": case["id"],
        "category": case["category"],
        "phase": "seed-validation",
        "status": "pass" if completed.returncode == seed_expected else "fail",
        "exit_code": completed.returncode,
        "seed_expected_exit_code": seed_expected,
        "solution_expected_exit_code": solution_expected,
        "elapsed_seconds": round(elapsed, 4),
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def main() -> None:
    results: list[dict[str, Any]] = []

    for case_dir in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        results.append(run_seed_oracle(case_dir, case))

    summary = {
        "phase": "seed-validation",
        "total": len(results),
        "passed": sum(r["status"] == "pass" for r in results),
        "failed": sum(r["status"] == "fail" for r in results),
        "metadata_only": sum(r["status"] == "metadata-only" for r in results),
        "results": results,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
