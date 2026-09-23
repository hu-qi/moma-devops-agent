"""Deterministic DevOpsBench v0.1 runner.

Two different questions are intentionally separated:

1. validate-fixtures:
   Is the benchmark case itself valid and does its initial state reproduce the
   intended defect/precondition?

2. evaluate:
   Does a candidate workspace satisfy the target oracle?

Agent execution is deliberately outside this module. Adapters prepare a
candidate workspace, then call the deterministic evaluator.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "cases"
RUNTIME_METRIC_FIELDS = {
    "duration_ms",
    "model_calls",
    "tool_calls",
    "input_tokens",
    "output_tokens",
    "estimated_cost",
    "human_interventions",
    "artifacts",
    "runtime_clean_completion",
}

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

    fixture = case.get("fixture")
    if not isinstance(fixture, dict) or not fixture.get("path"):
        raise ValueError(f"{case_dir.name}: fixture.path is required")

    oracle_type = case.get("oracle", {}).get("type")
    if oracle_type not in {"command-exit", "structured-review"}:
        raise ValueError(f"{case_dir.name}: unsupported oracle type: {oracle_type!r}")

    return case


def fixture_path(case_dir: Path, case: dict[str, Any]) -> Path:
    path = (case_dir / case["fixture"]["path"]).resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"{case_dir.name}: fixture not found: {path}")
    return path


def run_command(command: str, cwd: Path, timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def validate_precondition(case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    workspace = fixture_path(case_dir, case)
    precondition = case.get("precondition")
    if not precondition:
        return {
            "case_id": case["id"],
            "status": "error",
            "reason": "missing precondition",
        }

    kind = precondition.get("type")
    if kind == "command-exit":
        result = run_command(
            precondition["command"],
            workspace,
            int(case["budget"]["timeout_seconds"]),
        )
        expected = int(precondition["expected_exit_code"])
        return {
            "case_id": case["id"],
            "status": "pass" if result["exit_code"] == expected else "fail",
            "precondition_type": kind,
            "expected_exit_code": expected,
            **result,
        }

    if kind == "file-contains":
        target = workspace / precondition["path"]
        if not target.exists():
            return {
                "case_id": case["id"],
                "status": "fail",
                "precondition_type": kind,
                "reason": f"missing file: {precondition['path']}",
            }
        content = target.read_text(encoding="utf-8")
        missing = [needle for needle in precondition["contains"] if needle not in content]
        return {
            "case_id": case["id"],
            "status": "pass" if not missing else "fail",
            "precondition_type": kind,
            "missing_markers": missing,
        }

    return {
        "case_id": case["id"],
        "status": "error",
        "reason": f"unsupported precondition type: {kind!r}",
    }


def validate_fixtures() -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for case_dir in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
        try:
            case = load_case(case_dir)
            results.append(validate_precondition(case_dir, case))
        except Exception as exc:  # benchmark validation should report all cases
            results.append(
                {
                    "case_id": case_dir.name,
                    "status": "error",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )

    return {
        "mode": "validate-fixtures",
        "total": len(results),
        "passed": sum(r["status"] == "pass" for r in results),
        "failed": sum(r["status"] in {"fail", "error"} for r in results),
        "results": results,
    }


def load_runtime_metrics(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"runtime metrics file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        metrics = json.load(f)
    if not isinstance(metrics, dict):
        raise ValueError("runtime metrics must be a JSON object")

    unknown = sorted(set(metrics) - RUNTIME_METRIC_FIELDS)
    if unknown:
        raise ValueError(
            "unsupported runtime metric fields: " + ", ".join(unknown)
        )

    for key in (
        "duration_ms",
        "model_calls",
        "tool_calls",
        "input_tokens",
        "output_tokens",
        "human_interventions",
    ):
        if key in metrics:
            value = metrics[key]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ValueError(f"{key} must be a non-negative integer")

    if "estimated_cost" in metrics:
        value = metrics["estimated_cost"]
        if value is not None and (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value < 0
        ):
            raise ValueError("estimated_cost must be null or a non-negative number")

    if "runtime_clean_completion" in metrics:
        value = metrics["runtime_clean_completion"]
        if value is not None and not isinstance(value, bool):
            raise ValueError("runtime_clean_completion must be boolean or null")

    if "artifacts" in metrics:
        artifacts = metrics["artifacts"]
        if (
            not isinstance(artifacts, list)
            or not all(isinstance(item, str) for item in artifacts)
        ):
            raise ValueError("artifacts must be an array of strings")

    return metrics


def evaluate_command_oracle(
    case: dict[str, Any],
    workspace: Path,
    *,
    variant: str,
    run_id: str,
    runtime_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    oracle = case["oracle"]
    result = run_command(
        oracle["command"],
        workspace,
        int(case["budget"]["timeout_seconds"]),
    )
    expected = int(oracle["expected_exit_code"])
    success = result["exit_code"] == expected
    metrics = runtime_metrics or {}
    return {
        "case_id": case["id"],
        "run_id": run_id,
        "variant": variant,
        "status": "passed" if success else "failed",
        "task_success": success,
        "test_pass": success if case["category"] == "coding" else None,
        "ci_pass": success if case["category"] == "ci-debug" else None,
        "regression_count": 0,
        "duration_ms": metrics.get(
            "duration_ms",
            int(result["elapsed_seconds"] * 1000),
        ),
        "model_calls": metrics.get("model_calls", 0),
        "tool_calls": metrics.get("tool_calls", 0),
        "input_tokens": metrics.get("input_tokens", 0),
        "output_tokens": metrics.get("output_tokens", 0),
        "estimated_cost": metrics.get("estimated_cost"),
        "human_interventions": metrics.get("human_interventions", 0),
        "artifacts": metrics.get("artifacts", []),
        "runtime_clean_completion": metrics.get("runtime_clean_completion"),
        "failure_reason": None if success else result["stderr"] or result["stdout"],
        "evidence": {
            "oracle_type": "command-exit",
            "expected_exit_code": expected,
            "runtime_metrics_supplied": bool(metrics),
            **result,
        },
    }


def evaluate_case(
    case_id: str,
    workspace: Path,
    variant: str,
    run_id: str,
    runtime_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    match: tuple[Path, dict[str, Any]] | None = None
    for case_dir in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        if case["id"] == case_id or case_dir.name == case_id:
            match = (case_dir, case)
            break
    if match is None:
        raise ValueError(f"unknown case: {case_id}")

    _, case = match
    if not workspace.exists() or not workspace.is_dir():
        raise FileNotFoundError(f"candidate workspace not found: {workspace}")

    oracle_type = case["oracle"]["type"]
    if oracle_type == "command-exit":
        return evaluate_command_oracle(
            case,
            workspace.resolve(),
            variant=variant,
            run_id=run_id,
            runtime_metrics=runtime_metrics,
        )

    raise NotImplementedError(
        "structured-review candidate evaluation requires the Agent-result adapter "
        "and is intentionally not guessed by the deterministic runner"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DevOpsBench v0.1")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("validate-fixtures", help="Verify that benchmark initial states reproduce their intended defect")

    evaluate = sub.add_parser("evaluate", help="Evaluate a prepared candidate workspace")
    evaluate.add_argument("--case", required=True)
    evaluate.add_argument("--workspace", required=True)
    evaluate.add_argument("--variant", default="manual")
    evaluate.add_argument("--run-id", default=None)
    evaluate.add_argument(
        "--metrics-file",
        default=None,
        help=(
            "Optional JSON file containing observed runtime metrics such as "
            "model/tool calls and token usage. Oracle success is still "
            "determined independently by DevOpsBench."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    command = args.command or "validate-fixtures"

    if command == "validate-fixtures":
        result = validate_fixtures()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["failed"] == 0 else 1)

    if command == "evaluate":
        result = evaluate_case(
            args.case,
            Path(args.workspace),
            args.variant,
            args.run_id or f"run-{uuid.uuid4().hex[:12]}",
            load_runtime_metrics(
                Path(args.metrics_file).resolve()
                if args.metrics_file
                else None
            ),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result["task_success"] else 1)

    raise SystemExit(f"unsupported command: {command}")


if __name__ == "__main__":
    main()
