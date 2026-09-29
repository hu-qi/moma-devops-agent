"""C23: recompute comparison metrics from raw sweep JSONL.

Second-person reproducibility: anyone with the raw JSONL (written by
`runner.py sweep --execute`) can recompute every number shown in reports.
No metric may be invented upstream; if the raw file lacks it, the recomputed
table says so.

Pricing honesty: model prices come from the official MoMA price page
(https://ecloud.10086.cn/op-help-center/doc/article/91592). Cost is computed
ONLY when per-model unit prices are supplied via --prices JSON; otherwise
every cost cell is `unestimated` and is never reported as free/zero.

Usage:
    python benchmarks/devopsbench/recompute_metrics.py --raw raw.jsonl
    python benchmarks/devopsbench/recompute_metrics.py --raw raw.jsonl --prices prices.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

UNESTIMATED = "unestimated"


def load_records(path: Path) -> list[dict]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def recompute(records: list[dict], prices: dict[str, dict] | None = None) -> dict:
    by_variant: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        by_variant[r["variant"]].append(r)

    variants = {}
    for variant, runs in sorted(by_variant.items()):
        evaluated = [r for r in runs if not r.get("skipped")]
        skipped = [r for r in runs if r.get("skipped")]
        successes = [r for r in evaluated if r.get("task_success")]
        durations = [r["duration_ms"] for r in evaluated if isinstance(r.get("duration_ms"), (int, float)) and r["duration_ms"] > 0]
        tokens_in = [r["input_tokens"] for r in evaluated if isinstance(r.get("input_tokens"), (int, float))]
        tokens_out = [r["output_tokens"] for r in evaluated if isinstance(r.get("output_tokens"), (int, float))]
        interventions = [r.get("human_interventions", 0) for r in evaluated]

        failure_reasons: dict[str, int] = defaultdict(int)
        for r in runs:
            if r.get("skipped"):
                failure_reasons[f"skipped: {r.get('failure_reason', 'unknown')[:80]}"] += 1
            elif not r.get("task_success"):
                failure_reasons[str(r.get("failure_reason", "unknown"))[:120]] += 1

        # Run-to-run variance: show spread, not just the mean (C23).
        pass_rates_by_case: dict[str, list[int]] = defaultdict(list)
        for r in evaluated:
            pass_rates_by_case[r["case_id"]].append(1 if r.get("task_success") else 0)
        case_rates = [sum(v) / len(v) for v in pass_rates_by_case.values() if v]

        cost_status = UNESTIMATED
        total_cost = UNESTIMATED
        if prices:
            cost_total = 0.0
            priced_all = True
            for r in evaluated:
                model = str(r.get("coding_model") or r.get("model") or "")
                p = prices.get(model)
                if p is None:
                    priced_all = False
                    continue
                cost_total += (
                    r.get("input_tokens", 0) * p.get("input_per_1k", 0)
                    + r.get("output_tokens", 0) * p.get("output_per_1k", 0)
                ) / 1000.0
            cost_status = "computed" if priced_all else "partially_priced (missing models recorded as unestimated)"
            total_cost = round(cost_total, 6) if priced_all else UNESTIMATED

        variants[variant] = {
            "runs_total": len(runs),
            "runs_evaluated": len(evaluated),
            "runs_skipped": len(skipped),
            "success_rate": round(len(successes) / len(evaluated), 4) if evaluated else None,
            "duration_ms": {
                "mean": round(statistics.mean(durations), 1) if durations else None,
                "stdev": round(statistics.stdev(durations), 1) if len(durations) > 1 else 0.0,
                "note": "empty when raw file has no positive durations",
            },
            "tokens": {
                "input_mean": round(statistics.mean(tokens_in), 1) if tokens_in else None,
                "output_mean": round(statistics.mean(tokens_out), 1) if tokens_out else None,
            },
            "human_interventions_total": sum(interventions) if interventions else 0,
            "cost": {"status": cost_status, "total": total_cost},
            "case_pass_variance": {
                "per_case_pass_rate": {k: round(sum(v) / len(v), 3) for k, v in sorted(pass_rates_by_case.items())},
                "spread_note": "per-case mean over repeats; re-run variance is visible, not hidden",
            },
            "failure_reasons": dict(sorted(failure_reasons.items(), key=lambda kv: -kv[1])),
        }

    return {
        "source_records": len(records),
        "pricing_rule": (
            "cost computed only from --prices JSON; without verified MoMA prices "
            "(https://ecloud.10086.cn/op-help-center/doc/article/91592) cost is 'unestimated'"
        ),
        "variants": variants,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="C23: recompute sweep metrics from raw JSONL")
    parser.add_argument("--raw", required=True, help="raw JSONL from runner.py sweep --execute")
    parser.add_argument("--prices", default=None, help="optional JSON: {model: {input_per_1k, output_per_1k}}")
    parser.add_argument("--output", default=None, help="optional path to write the recomputed JSON")
    args = parser.parse_args()

    raw = Path(args.raw)
    if not raw.is_file():
        print(f"raw file not found: {raw}", file=sys.stderr)
        return 2

    prices = None
    if args.prices:
        prices = json.loads(Path(args.prices).read_text(encoding="utf-8"))

    result = recompute(load_records(raw), prices)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
