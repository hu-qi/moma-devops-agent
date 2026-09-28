#!/usr/bin/env python3
"""Unified offline test and smoke regression runner for DevOpsPilot.

Executes all offline suites without requiring live LLM credentials or remote writes.
Covers:
- 15 offline smoke test suites
- 3 direct metric/profiler assert scripts
- DevOpsBench fixture precondition verification (isolating intentionally failing benchmarks)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class CheckItem:
    category: str
    name: str
    script: Path
    args: tuple[str, ...] = ()


OFFLINE_CHECKS: tuple[CheckItem, ...] = (
    # 15 Offline Smoke Suites
    CheckItem("smoke", "provider-contract-smoke", ROOT / "experiments" / "provider-contract-smoke" / "main.py"),
    CheckItem("smoke", "model-routing-smoke", ROOT / "experiments" / "model-routing-smoke" / "main.py"),
    CheckItem("smoke", "trajectory-smoke", ROOT / "experiments" / "trajectory-smoke" / "main.py"),
    CheckItem("smoke", "delivery-loop-smoke", ROOT / "experiments" / "delivery-loop-smoke" / "main.py"),
    CheckItem("smoke", "delivery-state-store-smoke", ROOT / "experiments" / "delivery-state-store-smoke" / "main.py"),
    CheckItem("smoke", "durable-delivery-smoke", ROOT / "experiments" / "durable-delivery-smoke" / "main.py"),
    CheckItem("smoke", "git-publisher-smoke", ROOT / "experiments" / "git-publisher-smoke" / "main.py"),
    CheckItem("smoke", "delivery-pipeline-smoke", ROOT / "experiments" / "delivery-pipeline-smoke" / "main.py"),
    CheckItem("smoke", "autonomous-control-plane-smoke", ROOT / "experiments" / "autonomous-control-plane-smoke" / "main.py"),
    CheckItem("smoke", "remediation-adapter-smoke", ROOT / "experiments" / "remediation-adapter-smoke" / "main.py"),
    CheckItem("smoke", "evolution-gate-smoke", ROOT / "experiments" / "evolution-gate-smoke" / "main.py"),
    CheckItem("smoke", "github-reference-adapter-smoke", ROOT / "experiments" / "github-reference-adapter-smoke" / "main.py"),
    CheckItem("smoke", "cnb-reference-adapter-smoke", ROOT / "experiments" / "cnb-reference-adapter-smoke" / "main.py"),
    CheckItem("smoke", "atomgit-reference-adapter-smoke", ROOT / "experiments" / "atomgit-reference-adapter-smoke" / "main.py"),
    CheckItem("smoke", "industry-pack-smoke", ROOT / "experiments" / "industry-pack-smoke" / "main.py"),
    CheckItem("smoke", "review-gate-smoke", ROOT / "experiments" / "review-gate-smoke" / "main.py"),
    CheckItem("smoke", "ci-aggregator-smoke", ROOT / "experiments" / "ci-aggregator-smoke" / "main.py"),
    CheckItem("smoke", "controlled-verification-smoke", ROOT / "experiments" / "controlled-verification-smoke" / "main.py"),
    CheckItem("smoke", "runtime-lock-lifecycle-smoke", ROOT / "experiments" / "runtime-lock-lifecycle-smoke" / "main.py"),
    CheckItem("smoke", "delivery-verifier-smoke", ROOT / "experiments" / "delivery-verifier-smoke" / "main.py"),
    CheckItem("smoke", "durable-intent-lease-smoke", ROOT / "experiments" / "durable-intent-lease-smoke" / "main.py"),
    CheckItem("smoke", "remediation-budget-smoke", ROOT / "experiments" / "remediation-budget-smoke" / "main.py"),
    CheckItem("smoke", "checkpoint-resume-smoke", ROOT / "experiments" / "checkpoint-resume-smoke" / "main.py"),
    CheckItem("smoke", "execution-planner-smoke", ROOT / "experiments" / "execution-planner-smoke" / "main.py"),
    CheckItem("smoke", "cli-smoke", ROOT / "experiments" / "cli-smoke" / "main.py"),
    CheckItem("smoke", "delivery-report-smoke", ROOT / "experiments" / "delivery-report-smoke" / "main.py"),
    CheckItem("smoke", "industry-pack-contract-smoke", ROOT / "experiments" / "industry-pack-contract-smoke" / "main.py"),
    CheckItem("smoke", "industry-rule-engine-smoke", ROOT / "experiments" / "industry-rule-engine-smoke" / "main.py"),
    CheckItem("smoke", "industry-gate-runner-smoke", ROOT / "experiments" / "industry-gate-runner-smoke" / "main.py"),
    CheckItem("smoke", "structured-review-evaluator-smoke", ROOT / "experiments" / "structured-review-evaluator-smoke" / "main.py"),
    CheckItem("smoke", "routing-comparator-smoke", ROOT / "experiments" / "routing-comparator-smoke" / "main.py"),
    CheckItem("smoke", "governed-evolution-smoke", ROOT / "experiments" / "governed-evolution-smoke" / "main.py"),
    CheckItem("smoke", "end-to-end-integration-suite", ROOT / "experiments" / "end-to-end-integration-suite" / "main.py"),
    CheckItem("smoke", "failure-boundary-governance-smoke", ROOT / "experiments" / "failure-boundary-governance-smoke" / "main.py"),
    CheckItem("smoke", "demo-cli-smoke", ROOT / "experiments" / "demo-cli-smoke" / "main.py"),

    # 3 Direct Metric/Profiler Assertion Scripts
    CheckItem("script", "model-routing-profiler", ROOT / "experiments" / "model-routing-smoke" / "test_profiler.py"),
    CheckItem("script", "trajectory-metrics", ROOT / "experiments" / "trajectory-smoke" / "test_metrics.py"),
    CheckItem("script", "devopsbench-runtime-metrics", ROOT / "benchmarks" / "devopsbench" / "test_runtime_metrics.py"),

    # Fixture Precondition and Lifecycle Validation
    CheckItem("fixture", "fixture-lifecycle-smoke", ROOT / "experiments" / "fixture-lifecycle-smoke" / "main.py"),
    CheckItem("fixture", "devopsbench-validate-fixtures", ROOT / "benchmarks" / "devopsbench" / "runner.py", ("validate-fixtures",)),
)


def run_check(item: CheckItem, python_bin: str, env: dict[str, str]) -> tuple[bool, float, str]:
    cmd = [python_bin, str(item.script), *item.args]
    start = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        duration = time.perf_counter() - start
        if proc.returncode == 0:
            return True, duration, ""
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return False, duration, output
    except Exception as exc:
        duration = time.perf_counter() - start
        return False, duration, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DevOpsPilot offline test suite")
    parser.add_argument("--category", choices=["all", "smoke", "script", "fixture"], default="all")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    args = parser.parse_args()

    python_bin = sys.executable
    env = os.environ.copy()
    src_dir = str(ROOT / "src")
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = src_dir

    checks = [
        item for item in OFFLINE_CHECKS
        if args.category == "all" or item.category == args.category
    ]

    print(f"=== DevOpsPilot Offline Regression ({len(checks)} checks) ===")
    passed = 0
    failed = 0
    total_start = time.perf_counter()

    for item in checks:
        if not item.script.exists():
            print(f"[-] {item.category:<7} {item.name:<32} MISSING ({item.script})")
            failed += 1
            if args.fail_fast:
                break
            continue

        success, duration, error = run_check(item, python_bin, env)
        if success:
            passed += 1
            print(f"[+] {item.category:<7} {item.name:<32} PASS ({duration:.2f}s)")
        else:
            failed += 1
            print(f"[x] {item.category:<7} {item.name:<32} FAIL ({duration:.2f}s)")
            if error:
                indented = "\n".join(f"    {line}" for line in error.splitlines()[-15:])
                print(f"--- Error tail:\n{indented}\n---")
            if args.fail_fast:
                break

    total_duration = time.perf_counter() - total_start
    print("=" * 60)
    print(f"Summary: {passed} passed, {failed} failed in {total_duration:.2f}s")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
