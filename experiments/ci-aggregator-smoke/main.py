"""Smoke and boundary tests for CI runs aggregation and required checks enforcement."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.providers import CIRunRef, RepositoryRef
from devopspilot.orchestration.ci_aggregator import (
    CIAggregationStatus,
    aggregate_ci_runs,
)

REPO = RepositoryRef(
    provider_id="mock",
    repository_id="repo-1",
    full_name="org/repo",
)


def make_run(
    run_id: str,
    check_name: str,
    commit_sha: str,
    status: str = "completed",
    conclusion: str | None = "success",
    attempt: int = 1,
) -> CIRunRef:
    return CIRunRef(
        provider_id="mock",
        run_id=run_id,
        repository=REPO,
        status=status,
        conclusion=conclusion,
        commit_sha=commit_sha,
        check_name=check_name,
        attempt=attempt,
    )


def test_green_plus_required_red_blocks() -> None:
    head_sha = "commit-head"
    # Case that previously triggered false-positive pass: runs[0] is green, runs[1] is red
    runs = [
        make_run("run-1", "lint", head_sha, status="completed", conclusion="success"),
        make_run("run-2", "test", head_sha, status="completed", conclusion="failure"),
    ]
    res = aggregate_ci_runs(
        runs,
        expected_commit_sha=head_sha,
        required_checks=("lint", "test"),
    )
    assert res.status is CIAggregationStatus.FAILED
    assert res.primary_run is not None
    assert res.primary_run.run_id == "run-2"
    print("CI_AGGREGATOR_GREEN_PLUS_RED_BLOCKED_OK")


def test_missing_and_pending_required_checks() -> None:
    head_sha = "commit-head"
    # 1. Missing check
    runs = [
        make_run("run-1", "lint", head_sha, status="completed", conclusion="success"),
    ]
    res1 = aggregate_ci_runs(
        runs,
        expected_commit_sha=head_sha,
        required_checks=("lint", "test"),
    )
    assert res1.status is CIAggregationStatus.PENDING
    assert "test" in res1.missing_checks
    print("CI_AGGREGATOR_MISSING_PENDING_OK")

    # 2. Running check
    runs2 = [
        make_run("run-1", "lint", head_sha, status="completed", conclusion="success"),
        make_run("run-2", "test", head_sha, status="in_progress", conclusion=None),
    ]
    res2 = aggregate_ci_runs(
        runs2,
        expected_commit_sha=head_sha,
        required_checks=("lint", "test"),
    )
    assert res2.status is CIAggregationStatus.PENDING
    assert "test" in res2.pending_checks
    print("CI_AGGREGATOR_IN_PROGRESS_PENDING_OK")


def test_all_required_passed() -> None:
    head_sha = "commit-head"
    runs = [
        make_run("run-1", "lint", head_sha, status="completed", conclusion="success"),
        make_run("run-2", "test", head_sha, status="completed", conclusion="success"),
        # Unrelated third check failing should be ignored if not in required list
        make_run("run-3", "optional-docs", head_sha, status="completed", conclusion="failure"),
    ]
    res = aggregate_ci_runs(
        runs,
        expected_commit_sha=head_sha,
        required_checks=("lint", "test"),
    )
    assert res.status is CIAggregationStatus.PASSED
    assert len(res.matched_runs) == 2
    print("CI_AGGREGATOR_ALL_REQUIRED_PASSED_OK")


def test_old_commit_sha_and_attempts() -> None:
    head_sha = "commit-head"
    old_sha = "commit-old"
    runs = [
        # Old commit run had failed
        make_run("run-old", "test", old_sha, status="completed", conclusion="failure"),
        # Attempt 1 for head sha failed, attempt 2 succeeded
        make_run("run-head-1", "test", head_sha, status="completed", conclusion="failure", attempt=1),
        make_run("run-head-2", "test", head_sha, status="completed", conclusion="success", attempt=2),
    ]
    res = aggregate_ci_runs(
        runs,
        expected_commit_sha=head_sha,
        required_checks=("test",),
    )
    assert res.status is CIAggregationStatus.PASSED
    assert res.primary_run is not None
    assert res.primary_run.attempt == 2
    print("CI_AGGREGATOR_ATTEMPT_AND_SHA_FILTER_OK")


def main() -> None:
    test_green_plus_required_red_blocks()
    test_missing_and_pending_required_checks()
    test_all_required_passed()
    test_old_commit_sha_and_attempts()
    print("ALL CI AGGREGATOR SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
