"""Smoke test for StructuredReviewEvaluator: true/false positives, false negatives, precision, recall, and verdict matching."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks.devopsbench.review_evaluator import StructuredReviewEvaluator
from devopspilot.contracts.review import ReviewFinding, ReviewResult, ReviewVerdict


def test_evaluator_accurate_hit() -> None:
    evaluator = StructuredReviewEvaluator()
    candidate = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.REJECTED,
        diff_digest="sha256:111",
        findings=(
            ReviewFinding(path="app.py", message="Unsafe sql injection in query construction"),
            ReviewFinding(path="app.py", message="Use parameterized query instead of string formatting"),
        ),
        summary="Security flaws identified: sql-injection and missing parameterized-query",
    )
    oracle = {
        "expected_verdict": "rejected",
        "required_findings": [
            "sql-injection",
            "parameterized-query",
        ],
        "forbidden_false_positives": [
            "buffer-overflow",
        ],
        "min_recall": 1.0,
        "max_false_positives": 0,
    }

    res = evaluator.evaluate(candidate, oracle)
    assert res.passed is True
    assert res.verdict_matches is True
    assert res.true_positives == 2
    assert res.false_positives == 0
    assert res.false_negatives == 0
    assert res.precision == 1.0
    assert res.recall == 1.0
    assert res.f1_score == 1.0
    print("REVIEW_EVALUATOR_ACCURATE_HIT_OK")


def test_evaluator_detects_false_negative_leak() -> None:
    evaluator = StructuredReviewEvaluator()
    # Candidate only reported sql-injection, but missed parameterized-query
    candidate = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.REJECTED,
        diff_digest="sha256:222",
        findings=(
            ReviewFinding(path="app.py", message="Unsafe sql injection"),
        ),
        summary="Found sql-injection",
    )
    oracle = {
        "expected_verdict": "rejected",
        "required_findings": [
            "sql-injection",
            "parameterized-query",
        ],
        "min_recall": 1.0,
        "max_false_positives": 0,
    }

    res = evaluator.evaluate(candidate, oracle)
    assert res.passed is False
    assert res.true_positives == 1
    assert res.false_negatives == 1
    assert "parameterized-query" in res.missing_findings
    assert res.recall == 0.5
    print("REVIEW_EVALUATOR_FALSE_NEGATIVE_LEAK_DETECTED_OK")


def test_evaluator_detects_false_positive_spurious() -> None:
    evaluator = StructuredReviewEvaluator()
    # Candidate falsely claimed buffer-overflow on Python code
    candidate = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.REJECTED,
        diff_digest="sha256:333",
        findings=(
            ReviewFinding(path="app.py", message="sql-injection and parameterized-query"),
            ReviewFinding(path="app.py", message="buffer-overflow vulnerability"),
        ),
        summary="Found buffer-overflow",
    )
    oracle = {
        "expected_verdict": "rejected",
        "required_findings": [
            "sql-injection",
            "parameterized-query",
        ],
        "forbidden_false_positives": [
            "buffer-overflow",
        ],
        "min_recall": 1.0,
        "max_false_positives": 0,
    }

    res = evaluator.evaluate(candidate, oracle)
    assert res.passed is False
    assert res.true_positives == 2
    assert res.false_positives == 1
    assert "buffer-overflow" in res.spurious_findings
    print("REVIEW_EVALUATOR_FALSE_POSITIVE_DETECTED_OK")


def test_evaluator_verdict_mismatch_fails() -> None:
    evaluator = StructuredReviewEvaluator()
    # Should have rejected, but approved
    candidate = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.APPROVED,
        diff_digest="sha256:444",
        findings=(),
        summary="Looks clean",
    )
    oracle = {
        "expected_verdict": "rejected",
        "required_findings": ["sql-injection"],
    }

    res = evaluator.evaluate(candidate, oracle)
    assert res.passed is False
    assert res.verdict_matches is False
    assert "Verdict mismatch" in res.reason
    print("REVIEW_EVALUATOR_VERDICT_MISMATCH_OK")


def main() -> None:
    test_evaluator_accurate_hit()
    test_evaluator_detects_false_negative_leak()
    test_evaluator_detects_false_positive_spurious()
    test_evaluator_verdict_mismatch_fails()
    print("ALL STRUCTURED REVIEW EVALUATOR SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
