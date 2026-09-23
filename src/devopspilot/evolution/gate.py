"""Deterministic DevOpsBench regression gate for evolution candidates."""

from __future__ import annotations

from devopspilot.contracts.evolution import (
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionEvidence,
    EvolutionRequest,
)


class RegressionGate:
    def __init__(self, *, require_target_success: bool = True) -> None:
        self._require_target_success = require_target_success

    def evaluate(
        self,
        *,
        request: EvolutionRequest,
        candidate: EvolutionCandidate,
        baseline: tuple[BenchmarkObservation, ...],
        candidate_results: tuple[BenchmarkObservation, ...],
    ) -> EvolutionEvidence:
        base_by_case = {item.case_id: item for item in baseline}
        cand_by_case = {item.case_id: item for item in candidate_results}
        required = set(request.evaluation_cases)

        if set(base_by_case) != set(cand_by_case):
            raise ValueError("baseline and candidate must cover identical cases")
        missing = required - set(cand_by_case)
        if missing:
            raise ValueError(
                "missing requested evaluation cases: " + ", ".join(sorted(missing))
            )

        regressions: list[str] = []
        for case_id in sorted(cand_by_case):
            before = base_by_case[case_id]
            after = cand_by_case[case_id]
            if before.task_success and not after.task_success:
                regressions.append(f"{case_id}:task-success")
            if after.regression_count > before.regression_count:
                regressions.append(f"{case_id}:regression-count")
            if (
                before.runtime_clean_completion is True
                and after.runtime_clean_completion is False
            ):
                regressions.append(f"{case_id}:runtime-clean-completion")

        target_after = [cand_by_case[x] for x in request.evaluation_cases]
        target_before = [base_by_case[x] for x in request.evaluation_cases]

        improvements: list[str] = []
        if sum(x.task_success for x in target_after) > sum(
            x.task_success for x in target_before
        ):
            improvements.append("task_success")

        for name in ("tool_calls", "input_tokens", "output_tokens"):
            before_total = sum(getattr(x, name) for x in target_before)
            after_total = sum(getattr(x, name) for x in target_after)
            if after_total < before_total:
                improvements.append(name)

        if all(x.duration_ms is not None for x in target_before + target_after):
            before_duration = sum(int(x.duration_ms or 0) for x in target_before)
            after_duration = sum(int(x.duration_ms or 0) for x in target_after)
            if after_duration < before_duration:
                improvements.append("duration_ms")

        target_success_ok = (
            all(x.task_success for x in target_after)
            if self._require_target_success
            else True
        )
        gate_passed = bool(
            not regressions
            and improvements
            and target_success_ok
        )

        return EvolutionEvidence(
            candidate_id=candidate.candidate_id,
            baseline=baseline,
            candidate=candidate_results,
            improved_metrics=tuple(improvements),
            regressions=tuple(regressions),
            gate_passed=gate_passed,
        )
