"""Self-test for DevOpsBench observed runtime metrics."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


RUNNER_PATH = Path(__file__).with_name("runner.py")
spec = importlib.util.spec_from_file_location("devopsbench_runner", RUNNER_PATH)
assert spec is not None and spec.loader is not None
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main() -> None:
    root = Path(tempfile.mkdtemp(prefix="devopsbench_metrics_"))
    metrics_path = root / "metrics.json"
    metrics_path.write_text(json.dumps({
        "duration_ms": 1234,
        "model_calls": 3,
        "tool_calls": 7,
        "input_tokens": 1200,
        "output_tokens": 300,
        "estimated_cost": 0.42,
        "human_interventions": 1,
        "artifacts": ["trajectory.json"],
    }), encoding="utf-8")

    metrics = runner.load_runtime_metrics(metrics_path)
    assert metrics["model_calls"] == 3
    assert metrics["tool_calls"] == 7

    case = {
        "id": "metrics.smoke",
        "category": "coding",
        "oracle": {
            "type": "command-exit",
            "command": "python -c \"raise SystemExit(0)\"",
            "expected_exit_code": 0,
        },
        "budget": {"timeout_seconds": 5},
    }
    result = runner.evaluate_command_oracle(
        case,
        root,
        variant="metrics-smoke",
        run_id="metrics-smoke-1",
        runtime_metrics=metrics,
    )
    assert result["task_success"] is True
    assert result["duration_ms"] == 1234
    assert result["model_calls"] == 3
    assert result["tool_calls"] == 7
    assert result["input_tokens"] == 1200
    assert result["output_tokens"] == 300
    assert result["estimated_cost"] == 0.42
    assert result["human_interventions"] == 1
    assert result["artifacts"] == ["trajectory.json"]
    assert result["evidence"]["runtime_metrics_supplied"] is True

    bad = root / "bad.json"
    bad.write_text('{"unknown_metric": 1}', encoding="utf-8")
    try:
        runner.load_runtime_metrics(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown runtime metric fields must be rejected")

    print("DEVOPSBENCH_RUNTIME_METRICS_OK")
    print("DEVOPSBENCH_ORACLE_INDEPENDENCE_OK")
    print("DEVOPSBENCH_METRIC_SCHEMA_GUARD_OK")


if __name__ == "__main__":
    main()
