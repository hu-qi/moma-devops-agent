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

    if oracle_type == "structured-review":
        from benchmarks.devopsbench.review_evaluator import StructuredReviewEvaluator
        evaluator = StructuredReviewEvaluator()
        
        # Try loading candidate review result from workspace or metrics
        candidate_data = (runtime_metrics or {}).get("review_result")
        if candidate_data is None:
            review_file = workspace / "review_result.json"
            if review_file.exists():
                candidate_data = json.loads(review_file.read_text(encoding="utf-8"))
            else:
                candidate_data = {"verdict": "rejected", "findings": [], "summary": "No review result provided"}

        eval_result = evaluator.evaluate(candidate_data, case["oracle"])
        metrics = runtime_metrics or {}

        return {
            "case_id": case["id"],
            "run_id": run_id,
            "variant": variant,
            "status": "passed" if eval_result.passed else "failed",
            "task_success": eval_result.passed,
            "review_pass": eval_result.passed,
            "precision": eval_result.precision,
            "recall": eval_result.recall,
            "f1_score": eval_result.f1_score,
            "true_positives": eval_result.true_positives,
            "false_positives": eval_result.false_positives,
            "false_negatives": eval_result.false_negatives,
            "duration_ms": metrics.get("duration_ms", 0),
            "model_calls": metrics.get("model_calls", 0),
            "tool_calls": metrics.get("tool_calls", 0),
            "input_tokens": metrics.get("input_tokens", 0),
            "output_tokens": metrics.get("output_tokens", 0),
            "estimated_cost": metrics.get("estimated_cost"),
            "human_interventions": metrics.get("human_interventions", 0),
            "runtime_clean_completion": metrics.get("runtime_clean_completion"),
            "failure_reason": None if eval_result.passed else eval_result.reason,
            "evidence": {
                "oracle_type": "structured-review",
                **eval_result.to_dict(),
            },
        }

    raise ValueError(f"unsupported oracle type: {oracle_type!r}")


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

    sweep = sub.add_parser(
        "sweep",
        help=(
            "Plan or execute a same-case-same-budget comparison sweep. "
            "Without --execute it only prints the call scale and budget "
            "(C22: the operator must see the scale before any real model call)."
        ),
    )
    sweep.add_argument("--category", choices=["coding", "code-review", "ci-debug", "all"], default="all")
    sweep.add_argument("--repeats", type=int, default=3, help="Runs per case per variant (minimum 3 for C22)")
    sweep.add_argument("--variants", default="A0,A1,A2,A3", help="Comma-separated variant labels")
    sweep.add_argument(
        "--output",
        default=None,
        help="JSONL file for raw per-run records (required with --execute)",
    )
    sweep.add_argument(
        "--execute",
        action="store_true",
        help="Actually run the sweep (requires --output); without it only the plan is printed",
    )
    return parser


def plan_sweep(category: str, repeats: int, variants: list[str]) -> dict[str, Any]:
    """Compute the sweep scale without running anything (C22 transparency)."""
    cases = []
    for case_dir in sorted(p for p in CASES_DIR.iterdir() if p.is_dir()):
        case = load_case(case_dir)
        if category == "all" or case["category"] == category:
            cases.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "timeout_seconds": case["budget"]["timeout_seconds"],
                    "max_model_calls": case["budget"]["max_model_calls"],
                    "max_tool_calls": case["budget"]["max_tool_calls"],
                }
            )
    total_runs = len(cases) * len(variants) * repeats
    total_model_calls_cap = sum(
        c["max_model_calls"] for c in cases
    ) * len(variants) * repeats
    return {
        "mode": "plan_only (no model calls executed)",
        "category": category,
        "cases": len(cases),
        "case_ids": [c["id"] for c in cases],
        "variants": variants,
        "repeats_per_case": repeats,
        "total_runs": total_runs,
        "upper_bound_model_calls": total_model_calls_cap,
        "pricing_note": (
            "MoMA per-model unit prices: https://ecloud.10086.cn/op-help-center/doc/article/91592 "
            "(unverified prices are recorded as 'unestimated', never free)"
        ),
        "note": "Same case, same budget, same RC for all variants. Holdout cases (if marked) are excluded from tuning.",
    }


def run_sweep(category: str, repeats: int, variants: list[str], output: Path) -> dict[str, Any]:
    """Execute the sweep deterministically where possible and write raw JSONL.

    C22 honesty: this offline sweep re-evaluates existing candidate workspaces;
    it does NOT fabricate model outputs. Variants without a prepared workspace
    produce a skipped record, keeping the raw file auditable.
    """
    plan = plan_sweep(category, repeats, variants)
    plan["mode"] = "execute"
    records_written = 0
    with output.open("w", encoding="utf-8") as fh:
        for case_id in plan["case_ids"]:
            for variant in variants:
                for rep in range(1, repeats + 1):
                    run_id = f"{variant}-{case_id}-rep{rep}"
                    workspace = Path("benchmarks") / "workspaces" / variant / case_id
                    record: dict[str, Any] = {
                        "run_id": run_id,
                        "case_id": case_id,
                        "variant": variant,
                        "repeat": rep,
                    }
                    if workspace.is_dir():
                        try:
                            result = evaluate_case(case_id, workspace, variant, run_id)
                            record.update(result)
                            record["skipped"] = False
                        except Exception as exc:
                            record.update({"skipped": True, "failure_reason": f"evaluation error: {exc}"})
                    else:
                        record.update({
                            "skipped": True,
                            "failure_reason": (
                                f"no prepared workspace at {workspace}; run the real "
                                "delivery pipeline first — synthetic metrics are forbidden"
                            ),
                        })
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                    records_written += 1
    return {
        "mode": "execute",
        "output": str(output),
        "records_written": records_written,
        "plan": plan,
    }


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

    if command == "sweep":
        variants = [v.strip() for v in args.variants.split(",") if v.strip()]
        repeats = max(1, args.repeats)
        if not args.execute:
            print(json.dumps(plan_sweep(args.category, repeats, variants), ensure_ascii=False, indent=2))
            raise SystemExit(0)
        if not args.output:
            print("--execute requires --output (raw JSONL path)", file=sys.stderr)
            raise SystemExit(2)
        result = run_sweep(args.category, repeats, variants, Path(args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0)

    raise SystemExit(f"unsupported command: {command}")


if __name__ == "__main__":
    main()
