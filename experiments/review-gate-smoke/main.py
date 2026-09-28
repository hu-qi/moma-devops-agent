"""Smoke test for structured ReviewResult contracts and review gate enforcement."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.review import (
    MissingReviewError,
    ReviewFinding,
    ReviewGateError,
    ReviewRejectedError,
    ReviewResult,
    ReviewTimeoutError,
    ReviewVerdict,
    StaleReviewError,
    enforce_review_gate,
)


def test_review_contracts() -> None:
    diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-broken\n+fixed\n"
    digest = ReviewResult.calculate_diff_digest(diff)

    review = ReviewResult(
        reviewer_id="reviewer-agent-01",
        verdict=ReviewVerdict.APPROVED,
        diff_digest=digest,
        commit_sha="a1b2c3d4e5f6",
        findings=(
            ReviewFinding(
                path="app.py",
                line=2,
                severity="info",
                message="Clean fix for defect",
            ),
        ),
        summary="Changes verified and approved.",
    )

    assert review.is_approved is True
    assert review.reviewer_id == "reviewer-agent-01"
    assert review.verdict is ReviewVerdict.APPROVED
    assert len(review.findings) == 1
    assert review.findings[0].path == "app.py"
    print("REVIEW_CONTRACTS_OK")


def test_review_gate_enforcement() -> None:
    original_diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-broken\n+fixed\n"
    digest = ReviewResult.calculate_diff_digest(original_diff)

    # 1. Missing review -> blocked
    try:
        enforce_review_gate(review=None, current_diff=original_diff, require_review=True)
        assert False, "Should have raised MissingReviewError"
    except MissingReviewError as exc:
        assert "no review verdict recorded" in str(exc)
        print("REVIEW_GATE_MISSING_BLOCKED_OK")

    # 2. Verdict REJECTED -> blocked
    rejected_review = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.REJECTED,
        diff_digest=digest,
        summary="Security flaw detected",
    )
    try:
        enforce_review_gate(review=rejected_review, current_diff=original_diff, require_review=True)
        assert False, "Should have raised ReviewRejectedError"
    except ReviewRejectedError as exc:
        assert "rejected" in str(exc)
        print("REVIEW_GATE_REJECTED_BLOCKED_OK")

    # 3. Verdict TIMEOUT -> blocked
    timeout_review = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.TIMEOUT,
        diff_digest=digest,
        summary="Reviewer model timed out",
    )
    try:
        enforce_review_gate(review=timeout_review, current_diff=original_diff, require_review=True)
        assert False, "Should have raised ReviewTimeoutError"
    except ReviewTimeoutError as exc:
        assert "timed out" in str(exc)
        print("REVIEW_GATE_TIMEOUT_BLOCKED_OK")

    # 4. Stale review (diff modified after review) -> blocked
    modified_diff = "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-broken\n+tampered\n"
    approved_review = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.APPROVED,
        diff_digest=digest,
        summary="Looks good",
    )
    try:
        enforce_review_gate(review=approved_review, current_diff=modified_diff, require_review=True)
        assert False, "Should have raised StaleReviewError"
    except StaleReviewError as exc:
        assert "mismatch" in str(exc)
        print("REVIEW_GATE_STALE_DIFF_BLOCKED_OK")

    # 5. APPROVED with matching diff -> allowed
    enforce_review_gate(review=approved_review, current_diff=original_diff, require_review=True)
    print("REVIEW_GATE_APPROVED_PASSED_OK")


def main() -> None:
    test_review_contracts()
    test_review_gate_enforcement()
    print("ALL REVIEW GATE SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
