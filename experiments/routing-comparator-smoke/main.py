"""Smoke test for A0/A1/A2/A3 routing strategy comparator and Single Agent First cost-efficiency decisions."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks.devopsbench.routing_comparator import (
    BenchmarkRoutingComparator,
    BenchmarkRunRecord,
    RoutingStrategy,
)


def test_routing_comparison_and_single_agent_first_decision() -> None:
    records = [
        # A0: Fast single agent (high speed, lower pass rate on complex, low tokens)
        BenchmarkRunRecord(case_id="case-1", strategy=RoutingStrategy.A0_SINGLE_FAST, repeat_idx=1, passed=True, duration_ms=1200, input_tokens=800, output_tokens=200),
        BenchmarkRunRecord(case_id="case-2", strategy=RoutingStrategy.A0_SINGLE_FAST, repeat_idx=1, passed=False, duration_ms=1400, input_tokens=850, output_tokens=250, failure_reason="timeout"),
        BenchmarkRunRecord(case_id="case-3", strategy=RoutingStrategy.A0_SINGLE_FAST, repeat_idx=1, passed=False, duration_ms=1300, input_tokens=900, output_tokens=220, failure_reason="logic_error"),

        # A1: Frontier single agent (good pass rate, higher cost/time)
        BenchmarkRunRecord(case_id="case-1", strategy=RoutingStrategy.A1_SINGLE_CAPABLE, repeat_idx=1, passed=True, duration_ms=3000, input_tokens=2500, output_tokens=800),
        BenchmarkRunRecord(case_id="case-2", strategy=RoutingStrategy.A1_SINGLE_CAPABLE, repeat_idx=1, passed=True, duration_ms=3200, input_tokens=2600, output_tokens=850),
        BenchmarkRunRecord(case_id="case-3", strategy=RoutingStrategy.A1_SINGLE_CAPABLE, repeat_idx=1, passed=False, duration_ms=3100, input_tokens=2700, output_tokens=900, failure_reason="assertion_failed"),

        # A2: Dynamic single agent (smart routing: fast for simple, capable for hard)
        BenchmarkRunRecord(case_id="case-1", strategy=RoutingStrategy.A2_DYNAMIC_SINGLE, repeat_idx=1, passed=True, duration_ms=1300, input_tokens=900, output_tokens=250),
        BenchmarkRunRecord(case_id="case-2", strategy=RoutingStrategy.A2_DYNAMIC_SINGLE, repeat_idx=1, passed=True, duration_ms=3100, input_tokens=2600, output_tokens=800),
        BenchmarkRunRecord(case_id="case-3", strategy=RoutingStrategy.A2_DYNAMIC_SINGLE, repeat_idx=1, passed=True, duration_ms=3200, input_tokens=2700, output_tokens=850),

        # A3: Agent team (multi-agent coordination overhead, heavy tokens, same pass rate as A2)
        BenchmarkRunRecord(case_id="case-1", strategy=RoutingStrategy.A3_AGENT_TEAM, repeat_idx=1, passed=True, duration_ms=8500, input_tokens=9500, output_tokens=3200),
        BenchmarkRunRecord(case_id="case-2", strategy=RoutingStrategy.A3_AGENT_TEAM, repeat_idx=1, passed=True, duration_ms=9200, input_tokens=10200, output_tokens=3500),
        BenchmarkRunRecord(case_id="case-3", strategy=RoutingStrategy.A3_AGENT_TEAM, repeat_idx=1, passed=True, duration_ms=8900, input_tokens=9800, output_tokens=3400),
    ]

    summaries = {
        s: BenchmarkRoutingComparator.summarize_strategy(s, records)
        for s in RoutingStrategy
    }

    # 1. Verify A0 stats
    a0 = summaries[RoutingStrategy.A0_SINGLE_FAST]
    assert a0.total_runs == 3
    assert a0.passed_runs == 1
    assert round(a0.pass_rate, 2) == 0.33
    assert a0.failure_distribution == {"timeout": 1, "logic_error": 1}
    assert a0.avg_cost is None  # Unknown pricing must be None, NEVER 0.0!
    print("A0_STATS_AND_FAILURE_REASONS_OK")

    # 2. Verify A2 stats
    a2 = summaries[RoutingStrategy.A2_DYNAMIC_SINGLE]
    assert a2.pass_rate == 1.0

    # 3. Verify A3 stats and overhead comparison
    a3 = summaries[RoutingStrategy.A3_AGENT_TEAM]
    assert a3.pass_rate == 1.0
    assert a3.avg_tokens > a2.avg_tokens * 3  # Team used > 3x tokens for the same 100% pass rate

    # 4. Verify Decision Maker enforces Single Agent First
    decision = BenchmarkRoutingComparator.compare_and_decide(summaries)
    # A3 has 0% net gain over A2, so A2 MUST be recommended
    assert decision["recommended_strategy"] == RoutingStrategy.A2_DYNAMIC_SINGLE.value
    assert "Single Agent First policy applies" in decision["decision_rationale"]
    print("SINGLE_AGENT_FIRST_DECISION_OK")


def main() -> None:
    test_routing_comparison_and_single_agent_first_decision()
    print("ALL ROUTING COMPARATOR SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
