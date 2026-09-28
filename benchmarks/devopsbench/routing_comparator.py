"""A0/A1/A2/A3 benchmark routing comparator evaluating cost-efficiency between Single Agent and Team."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence


class RoutingStrategy(StrEnum):
    A0_SINGLE_FAST = "A0_single_fast"        # Single agent with fast/lightweight model
    A1_SINGLE_CAPABLE = "A1_single_capable"  # Single agent with frontier/reasoning model
    A2_DYNAMIC_SINGLE = "A2_dynamic_single"  # Single agent with dynamic complexity-based routing
    A3_AGENT_TEAM = "A3_agent_team"          # Multi-agent team (Leader + Coder + Reviewer)


@dataclass(frozen=True, slots=True)
class BenchmarkRunRecord:
    case_id: str
    strategy: RoutingStrategy
    repeat_idx: int
    passed: bool
    duration_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost: float | None = None  # None if pricing is unknown; NEVER recorded as 0.0
    human_interventions: int = 0
    failure_reason: str | None = None


@dataclass(frozen=True, slots=True)
class StrategyEvaluationSummary:
    strategy: RoutingStrategy
    total_runs: int
    passed_runs: int
    pass_rate: float
    avg_duration_ms: float
    avg_tokens: float
    avg_cost: float | None
    human_interventions: int
    failure_distribution: Mapping[str, int] = field(default_factory=dict)
    recommendation_rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy.value,
            "total_runs": self.total_runs,
            "passed_runs": self.passed_runs,
            "pass_rate": round(self.pass_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "avg_tokens": round(self.avg_tokens, 2),
            "avg_cost": round(self.avg_cost, 6) if self.avg_cost is not None else None,
            "cost_status": "estimated" if self.avg_cost is not None else "unestimated",
            "human_interventions": self.human_interventions,
            "failure_distribution": dict(self.failure_distribution),
            "recommendation_rationale": self.recommendation_rationale,
        }


class BenchmarkRoutingComparator:
    """Compares A0/A1/A2/A3 routing strategies under identical benchmarks and budgets."""

    @classmethod
    def summarize_strategy(
        cls,
        strategy: RoutingStrategy,
        records: Sequence[BenchmarkRunRecord],
    ) -> StrategyEvaluationSummary:
        strategy_records = [r for r in records if r.strategy == strategy]
        if not strategy_records:
            return StrategyEvaluationSummary(
                strategy=strategy,
                total_runs=0,
                passed_runs=0,
                pass_rate=0.0,
                avg_duration_ms=0.0,
                avg_tokens=0.0,
                avg_cost=None,
                human_interventions=0,
                failure_distribution={},
                recommendation_rationale="No runs executed",
            )

        total = len(strategy_records)
        passed = sum(1 for r in strategy_records if r.passed)
        pass_rate = passed / total
        avg_dur = sum(r.duration_ms for r in strategy_records) / total
        avg_tok = sum(r.input_tokens + r.output_tokens for r in strategy_records) / total

        # Handle cost: if ANY record has unknown cost (None), average cost is marked unestimated
        costs = [r.estimated_cost for r in strategy_records if r.estimated_cost is not None]
        avg_cost = sum(costs) / len(costs) if len(costs) == total else None

        interventions = sum(r.human_interventions for r in strategy_records)

        failures: dict[str, int] = {}
        for r in strategy_records:
            if not r.passed and r.failure_reason:
                failures[r.failure_reason] = failures.get(r.failure_reason, 0) + 1

        return StrategyEvaluationSummary(
            strategy=strategy,
            total_runs=total,
            passed_runs=passed,
            pass_rate=pass_rate,
            avg_duration_ms=avg_dur,
            avg_tokens=avg_tok,
            avg_cost=avg_cost,
            human_interventions=interventions,
            failure_distribution=failures,
        )

    @classmethod
    def compare_and_decide(
        cls,
        summaries: Mapping[RoutingStrategy, StrategyEvaluationSummary],
    ) -> dict[str, Any]:
        """Produce actionable recommendation adhering to Single Agent First."""
        a0 = summaries.get(RoutingStrategy.A0_SINGLE_FAST)
        a1 = summaries.get(RoutingStrategy.A1_SINGLE_CAPABLE)
        a2 = summaries.get(RoutingStrategy.A2_DYNAMIC_SINGLE)
        a3 = summaries.get(RoutingStrategy.A3_AGENT_TEAM)

        recommendation = RoutingStrategy.A2_DYNAMIC_SINGLE
        rationale = "A2 Dynamic Single Agent balances latency, token consumption, and pass rate."

        # If Team doesn't significantly outperform Dynamic Single Agent (e.g. within 5% pass rate),
        # but uses substantially more tokens, do NOT recommend Team.
        if a2 and a3:
            pass_rate_diff = a3.pass_rate - a2.pass_rate
            token_multiplier = (a3.avg_tokens / a2.avg_tokens) if a2.avg_tokens > 0 else 1.0

            if pass_rate_diff <= 0.05:
                recommendation = RoutingStrategy.A2_DYNAMIC_SINGLE
                rationale = (
                    f"A3 Agent Team achieves {a3.pass_rate:.1%} pass rate vs {a2.pass_rate:.1%} for A2, "
                    f"with {token_multiplier:.1f}x token overhead. Zero/marginal net gain; "
                    "Single Agent First policy applies: recommend A2 Dynamic Single Agent."
                )
            else:
                recommendation = RoutingStrategy.A3_AGENT_TEAM
                rationale = (
                    f"A3 Agent Team achieves significant net gain (+{pass_rate_diff:.1%}) on complex tasks, "
                    "justifying the multi-specialist coordination overhead."
                )

        return {
            "recommended_strategy": recommendation.value,
            "decision_rationale": rationale,
            "summaries": {k.value: v.to_dict() for k, v in summaries.items()},
        }
