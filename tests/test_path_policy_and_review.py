"""C09: shared path policy and review-gate negative cases.

Validates: absolute paths, '..' traversal, symlink escapes, forbidden path
hits, allow-list violations, and empty / rejected / stale review blocking.
"""

import os
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from devopspilot.contracts.review import (
    MissingReviewError,
    ReviewResult,
    ReviewVerdict,
    StaleReviewError,
    enforce_review_gate,
)
from devopspilot.orchestration.path_policy import (
    PathPolicyConfigError,
    PathPolicyError,
    normalize_policy_paths,
    validate_changed_paths,
)


def test_normalize_rejects_absolute_and_traversal() -> None:
    try:
        normalize_policy_paths("/etc/passwd", "")
        raise AssertionError("absolute allowed path must be rejected")
    except PathPolicyConfigError:
        pass
    try:
        normalize_policy_paths("", "../secrets")
        raise AssertionError("'..' forbidden path must be rejected")
    except PathPolicyConfigError:
        pass
    print("PATH_POLICY_CONFIG_REJECTED_OK")


def test_normalize_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "workspace" / "link"
    link.parent.mkdir()
    os.symlink(outside, link)
    # policy entry routes through the symlink to outside the workspace
    try:
        normalize_policy_paths("link/../../etc", "", workspace_path=link.parent)
        raise AssertionError("symlink escape must be rejected")
    except PathPolicyConfigError:
        pass
    print("PATH_POLICY_SYMLINK_REJECTED_OK")


def test_validate_changed_paths_blocks_escapes_and_violations() -> None:
    # path escaping the workspace
    for bad in ("/etc/passwd", "../secrets"):
        try:
            validate_changed_paths({bad}, allowed=(), forbidden=())
            raise AssertionError(f"changed path '{bad}' must be rejected")
        except PathPolicyError:
            pass
    # forbidden hit
    try:
        validate_changed_paths({"tests/test_oracle.py"}, allowed=(), forbidden=("tests/test_oracle.py",))
        raise AssertionError("forbidden path must be rejected")
    except PathPolicyError:
        pass
    # allow-list violation
    try:
        validate_changed_paths({"src/other.py"}, allowed=("src/app.py",), forbidden=())
        raise AssertionError("path outside allow-list must be rejected")
    except PathPolicyError:
        pass
    # happy path
    validate_changed_paths({"src/app.py"}, allowed=("src/app.py", "src/"), forbidden=())
    print("PATH_POLICY_CHANGED_PATHS_OK")


def _approved_review(diff: str) -> ReviewResult:
    return ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.APPROVED,
        diff_digest=ReviewResult.calculate_diff_digest(diff),
    )


def test_review_gate_blocks_empty_rejected_and_stale() -> None:
    diff = "diff --git a/app.py b/app.py\n+print(1)\n"

    # empty / missing review is blocked
    try:
        enforce_review_gate(review=None, current_diff=diff, require_review=True)
        raise AssertionError("missing review must be blocked")
    except MissingReviewError:
        pass

    # rejected verdict is blocked
    rejected = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.REJECTED,
        diff_digest=ReviewResult.calculate_diff_digest(diff),
    )
    try:
        enforce_review_gate(review=rejected, current_diff=diff, require_review=True)
        raise AssertionError("rejected review must be blocked")
    except Exception as exc:
        assert type(exc).__name__ == "ReviewRejectedError"

    # stale digest is blocked
    stale = _approved_review("diff --git a/old.py b/old.py\n+x\n")
    try:
        enforce_review_gate(review=stale, current_diff=diff, require_review=True)
        raise AssertionError("stale review must be blocked")
    except StaleReviewError:
        pass

    # matching approval passes
    enforce_review_gate(review=_approved_review(diff), current_diff=diff, require_review=True)
    print("REVIEW_GATE_NEGATIVES_OK")


def test_executor_uses_shared_path_policy() -> None:
    # C09: the runtime (OpenJiuwen) executor must route through the shared
    # policy module, not its own ad-hoc string set comparison.
    source = (Path(__file__).resolve().parents[1] / "src" / "devopspilot" / "adapters" / "openjiuwen" / "executor.py").read_text(encoding="utf-8")
    assert "normalize_policy_paths" in source
    assert "validate_changed_paths" in source
    print("EXECUTOR_SHARED_POLICY_OK")


def main() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        test_normalize_rejects_symlink_escape(Path(td))
    test_normalize_rejects_absolute_and_traversal()
    test_validate_changed_paths_blocks_escapes_and_violations()
    test_review_gate_blocks_empty_rejected_and_stale()
    test_executor_uses_shared_path_policy()
    print("ALL C09 PATH POLICY AND REVIEW GATE TESTS PASSED.")


if __name__ == "__main__":
    main()
