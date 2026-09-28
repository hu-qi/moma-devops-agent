"""Aggregation and evaluation policies for multiple CI workflow runs and required checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Sequence

from devopspilot.contracts.providers import CIRunRef


class CIAggregationStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CIAggregationResult:
    status: CIAggregationStatus
    matched_runs: tuple[CIRunRef, ...]
    primary_run: CIRunRef | None = None
    failed_runs: tuple[CIRunRef, ...] = ()
    missing_checks: tuple[str, ...] = ()
    pending_checks: tuple[str, ...] = ()
    summary: str = ""


def normalize_check_identity(run: CIRunRef) -> str:
    """Derive standard check/workflow identity from CIRunRef."""
    if run.check_name:
        return run.check_name.strip()
    return run.run_id.strip()


def aggregate_ci_runs(
    runs: Sequence[CIRunRef],
    *,
    expected_commit_sha: str,
    required_checks: Sequence[str] | None = None,
) -> CIAggregationResult:
    """Aggregate CI runs against an expected HEAD commit SHA and required check set.

    Guarantees:
    - Runs from older or different commit SHAs are ignored.
    - Multiple attempts for the same check identity are deduplicated to the latest attempt.
    - If required_checks are specified, all must exist and pass.
    - Any failure in required checks immediately yields FAILED (green + red -> FAILED).
    - Any missing or in-progress required check yields PENDING.
    """
    # 1. Filter by exact commit_sha
    sha_matched = [
        r for r in runs
        if r.commit_sha is None or r.commit_sha == expected_commit_sha
    ]

    # 2. Group by check identity and select latest attempt
    latest_by_id: dict[str, CIRunRef] = {}
    for r in sha_matched:
        ident = normalize_check_identity(r)
        existing = latest_by_id.get(ident)
        if existing is None or r.attempt >= existing.attempt:
            latest_by_id[ident] = r

    req_set = tuple(dict.fromkeys(c.strip() for c in required_checks if c.strip())) if required_checks else ()

    if req_set:
        # Evaluate against declared required checks
        matched_required: list[CIRunRef] = []
        missing: list[str] = []
        pending: list[str] = []
        failed: list[CIRunRef] = []

        for req in req_set:
            run = latest_by_id.get(req)
            if run is None:
                missing.append(req)
                continue
            matched_required.append(run)
            if run.status != "completed" and run.conclusion is None:
                pending.append(req)
            elif run.conclusion in {"failure", "timed_out", "cancelled", "action_required"}:
                failed.append(run)
            elif run.conclusion != "success":
                failed.append(run)

        # Failure takes highest priority: green + required red -> FAILED
        if failed:
            return CIAggregationResult(
                status=CIAggregationStatus.FAILED,
                matched_runs=tuple(matched_required),
                primary_run=failed[0],
                failed_runs=tuple(failed),
                missing_checks=tuple(missing),
                pending_checks=tuple(pending),
                summary=f"Required CI check(s) failed: {', '.join(normalize_check_identity(f) for f in failed)}",
            )

        # Missing or in-progress checks -> PENDING
        if missing or pending:
            reasons = []
            if missing:
                reasons.append(f"missing [{', '.join(missing)}]")
            if pending:
                reasons.append(f"running [{', '.join(pending)}]")
            return CIAggregationResult(
                status=CIAggregationStatus.PENDING,
                matched_runs=tuple(matched_required),
                missing_checks=tuple(missing),
                pending_checks=tuple(pending),
                summary=f"Waiting for required CI: {'; '.join(reasons)}",
            )

        # All required present and successful
        return CIAggregationResult(
            status=CIAggregationStatus.PASSED,
            matched_runs=tuple(matched_required),
            primary_run=matched_required[0] if matched_required else None,
            summary=f"All {len(req_set)} required checks passed",
        )

    # If no required_checks specified: aggregate all runs matching expected commit
    if not sha_matched:
        return CIAggregationResult(
            status=CIAggregationStatus.PENDING,
            matched_runs=(),
            summary=f"No CI runs detected for commit {expected_commit_sha}",
        )

    all_latest = tuple(latest_by_id.values())
    failed = [
        r for r in all_latest
        if r.conclusion in {"failure", "timed_out", "cancelled", "action_required"}
        or (r.status == "completed" and r.conclusion != "success")
    ]
    if failed:
        return CIAggregationResult(
            status=CIAggregationStatus.FAILED,
            matched_runs=all_latest,
            primary_run=failed[0],
            failed_runs=tuple(failed),
            summary=f"CI failed on {len(failed)} run(s)",
        )

    pending_runs = [
        r for r in all_latest
        if r.status != "completed" and r.conclusion is None
    ]
    if pending_runs:
        return CIAggregationResult(
            status=CIAggregationStatus.PENDING,
            matched_runs=all_latest,
            primary_run=pending_runs[0],
            pending_checks=tuple(normalize_check_identity(p) for p in pending_runs),
            summary=f"Waiting for {len(pending_runs)} in-progress CI run(s)",
        )

    return CIAggregationResult(
        status=CIAggregationStatus.PASSED,
        matched_runs=all_latest,
        primary_run=all_latest[0] if all_latest else None,
        summary=f"All {len(all_latest)} CI runs passed",
    )
