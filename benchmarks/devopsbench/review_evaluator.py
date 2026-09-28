"""Structured Review Evaluator calculating Precision, Recall, F1, and distinguishing True/False Positives/Negatives."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from devopspilot.contracts.review import ReviewFinding, ReviewResult, ReviewVerdict


@dataclass(frozen=True, slots=True)
class ReviewEvaluationMetrics:
    passed: bool
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float
    verdict_matches: bool
    expected_verdict: str
    actual_verdict: str
    matched_findings: tuple[str, ...] = ()
    missing_findings: tuple[str, ...] = ()
    spurious_findings: tuple[str, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "verdict_matches": self.verdict_matches,
            "expected_verdict": self.expected_verdict,
            "actual_verdict": self.actual_verdict,
            "matched_findings": list(self.matched_findings),
            "missing_findings": list(self.missing_findings),
            "spurious_findings": list(self.spurious_findings),
            "reason": self.reason,
        }


class StructuredReviewEvaluator:
    """Evaluates a candidate review result against a ground-truth review oracle.

    Distinguishes:
    - True Positives (TP): expected vulnerability/defect correctly identified
    - False Negatives (FN): expected vulnerability missed by reviewer (leak)
    - False Positives (FP): incorrect defect flagged or forbidden false positive triggered
    """

    def evaluate(
        self,
        candidate_review: ReviewResult | Mapping[str, Any],
        oracle: Mapping[str, Any],
    ) -> ReviewEvaluationMetrics:
        # Extract candidate properties
        if isinstance(candidate_review, ReviewResult):
            actual_verdict = candidate_review.verdict.value.lower()
            findings_text = " ".join(
                f"{f.path} {f.message}" for f in candidate_review.findings
            )
            raw_findings = [f.message for f in candidate_review.findings]
            if candidate_review.summary:
                findings_text += f" {candidate_review.summary}"
        else:
            actual_verdict = str(candidate_review.get("verdict", "rejected")).lower()
            findings_list = candidate_review.get("findings", [])
            findings_text = " ".join(str(f) for f in findings_list)
            if "summary" in candidate_review:
                findings_text += f" {candidate_review['summary']}"
            raw_findings = [str(f) for f in findings_list]

        expected_verdict = str(oracle.get("expected_verdict", "rejected")).lower()
        verdict_matches = (actual_verdict == expected_verdict)

        required_findings = tuple(str(x) for x in oracle.get("required_findings", ()))
        forbidden_findings = tuple(str(x) for x in oracle.get("forbidden_false_positives", ()))
        min_recall = float(oracle.get("min_recall", 1.0 if required_findings else 0.0))
        max_fp = int(oracle.get("max_false_positives", 0))

        matched: list[str] = []
        missing: list[str] = []
        findings_text_lower = findings_text.lower()

        # 1. Evaluate Recall against required findings (ground truth defects)
        for req in required_findings:
            req_clean = req.lower().replace("-", " ")
            if req_clean in findings_text_lower or req.lower() in findings_text_lower:
                matched.append(req)
            else:
                missing.append(req)

        tp = len(matched)
        fn = len(missing)

        # 2. Evaluate False Positives
        spurious: list[str] = []
        for forb in forbidden_findings:
            forb_clean = forb.lower().replace("-", " ")
            if forb_clean in findings_text_lower or forb.lower() in findings_text_lower:
                spurious.append(forb)

        # In clean-code scenarios where expected_verdict is "approved" and no defects exist,
        # any rejection or defect finding is treated as a False Positive
        if expected_verdict == "approved" and actual_verdict != "approved":
            spurious.append(f"spurious_rejection_with_verdict_{actual_verdict}")

        fp = len(spurious)

        # Calculate metrics
        precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fp == 0 else 0.0)
        recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Success criteria
        passed = (
            verdict_matches
            and recall >= min_recall
            and fp <= max_fp
        )

        reasons = []
        if not verdict_matches:
            reasons.append(f"Verdict mismatch: expected '{expected_verdict}', got '{actual_verdict}'")
        if missing:
            reasons.append(f"Missed {len(missing)} expected finding(s): {', '.join(missing)}")
        if spurious:
            reasons.append(f"Reported {len(spurious)} false positive(s): {', '.join(spurious)}")

        return ReviewEvaluationMetrics(
            passed=passed,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            verdict_matches=verdict_matches,
            expected_verdict=expected_verdict,
            actual_verdict=actual_verdict,
            matched_findings=tuple(matched),
            missing_findings=tuple(missing),
            spurious_findings=tuple(spurious),
            reason="; ".join(reasons) if reasons else "All review criteria satisfied.",
        )
