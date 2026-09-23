"""Minimal deterministic DevOpsBench runner.

V0.1 validates benchmark metadata and the seeded fixture precondition.
Agent execution is intentionally not coupled to this runner yet.

Contract:
- precondition: what must be true before the Agent starts;
- oracle: what must be true after the Agent finishes.
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

REQUIRED_FIELDS = {
    "id",
    "version",
    "category",
    "title",
    "task",
    "fixture",
    "constraints",
    "oracle",
    "budget",
    "risk",
    "provenance",
}


def load_case(case_dir: Path) -> dict[str, Any]:
    with (case_dir / "case.json").open("r", encoding="utf-8") as f:
        case = json.load(f)

    missing = sorted(REQUIRED_FIELDS - set(case))
    if missing:
        raise ValueError(f"{case_dir.name}: missing fields: {', '.join(missing)}")
    return case


def _run_command(workspace: Path, command: str, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=workspace,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def validate_seed(case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    fixture_src = case_dir / case["fixture"]["path"]
    if not fixture_src.exists():
        raise FileNotFoundError(f"fixture not found: {fixture_src}")

    precondition = case.get("precondition")
    if not precondition:
        return {
            "case_id": case["id"],
            "category": case["category"],
            "phase": "seed-validation",
            "status": "metadata-only",
        }

    started = time.perf_counter()
    timeout = int(case.get("budget", {}).get("timeout_seconds", 60))

    with tempfile.TemporaryDirectory(prefix="devopsbench-") as td:
        workspace = Path(td) / "workspace"
        shutil.copytree(fixture_src, workspace)

        if precondition["type"] == "command-exit":
            completed = _run_command(workspace, precondition["command"], timeout)
            expected = int(precondition["expected_exit_code"])
            ok = completed.returncode == expected
            detail = {
                "exit_code": completed.returncode,
                "expected_exit_code": expected,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        elif precondition["type"] == "file-contains":
            target = workspace / precondition["path"]
            body = target.read_text(encoding="utf-8")
            missing = [item for item in precondition["contains"] if item not in body]
            ok = not missing
            detail = {"missing_fragments": missing}
        else:
            raise ValueError(f"{case['id']}: unsupported precondition type: {precondition['type']}")

    return {
        "case_id": case["id"],
        "category": case["category"],
        "phase": "seed-validation",
        "status": "pass" if ok else "fail",
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        **detail,
    }


def main() -> None:
    results: list[dict[str, Any]] = []

    for case_dir in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        results.append(validate_seed(case_dir, case))

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
