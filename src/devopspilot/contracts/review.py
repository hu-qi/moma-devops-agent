"""Reviewer contracts, structured verdicts, and gate policies."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping


class ReviewVerdict(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    TIMEOUT = "timeout"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    path: str
    message: str
    line: int | None = None
    severity: str = "warning"


@dataclass(frozen=True, slots=True)
class ReviewResult:
    """Type-safe, serializable review verdict bound to reviewer identity and diff digest."""

    reviewer_id: str
    verdict: ReviewVerdict
    diff_digest: str
    commit_sha: str = ""
    findings: tuple[ReviewFinding, ...] = ()
    summary: str = ""
    created_at: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def calculate_diff_digest(cls, diff_text: str) -> str:
        """Compute SHA256 digest of normalized diff content."""
        normalized = diff_text.strip().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

    @property
    def is_approved(self) -> bool:
        return self.verdict is ReviewVerdict.APPROVED


class ReviewGateError(RuntimeError):
    """Raised when review gate denies commit or publication."""


class MissingReviewError(ReviewGateError):
    """Review is required but missing."""


class ReviewRejectedError(ReviewGateError):
    """Review verdict rejected the change."""


class StaleReviewError(ReviewGateError):
    """Review verdict does not match current diff digest."""


class ReviewTimeoutError(ReviewGateError):
    """Review timed out."""


def enforce_review_gate(
    *,
    review: ReviewResult | None,
    current_diff: str,
    require_review: bool = True,
) -> None:
    """Enforce strict review gate rules.

    - If review is required and missing -> MissingReviewError
    - If verdict is TIMEOUT -> ReviewTimeoutError
    - If verdict is not APPROVED -> ReviewRejectedError
    - If diff digest does not match current diff -> StaleReviewError
    """
    if not require_review:
        return

    if review is None:
        raise MissingReviewError("Mandatory review is missing: no review verdict recorded")

    if review.verdict is ReviewVerdict.TIMEOUT:
        raise ReviewTimeoutError(f"Review timed out (reviewer={review.reviewer_id})")

    if review.verdict is not ReviewVerdict.APPROVED:
        raise ReviewRejectedError(
            f"Review rejected changes with verdict={review.verdict} "
            f"(reviewer={review.reviewer_id}): {review.summary}"
        )

    current_digest = ReviewResult.calculate_diff_digest(current_diff)
    if review.diff_digest != current_digest:
        raise StaleReviewError(
            f"Review diff digest mismatch (stale verdict). "
            f"Reviewed digest={review.diff_digest}, current digest={current_digest}"
        )
