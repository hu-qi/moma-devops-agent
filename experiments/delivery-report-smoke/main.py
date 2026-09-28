"""Smoke test for DeliveryReportService, Markdown/JSON alignment, and full audit trail."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
    VerificationResult,
)
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.contracts.remediation import (
    CIFailureKind,
    RemediationAction,
    RemediationOutcome,
    RemediationRecord,
    RemediationStatus,
)
from devopspilot.contracts.review import ReviewFinding, ReviewResult, ReviewVerdict
from devopspilot.contracts.state import StoredDeliveryState
from devopspilot.orchestration.report_service import DeliveryReportService

REPO = RepositoryRef(provider_id="mock", repository_id="repo-report", full_name="org/report-repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="101", title="implement auth cache")


def test_delivery_report_generation() -> None:
    task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
    review = ReviewResult(
        reviewer_id="reviewer-01",
        verdict=ReviewVerdict.APPROVED,
        diff_digest="sha256:abcd1234ef",
        findings=(ReviewFinding(path="auth.py", message="looks solid", line=10),),
        summary="All checks approved.",
    )
    execution = ExecutionResult(
        source_branch="feat/auth-cache",
        commit_sha="a1b2c3d4e5f67890",
        summary="added auth caching with ttl",
        published=True,
        test_summary="pytest: 4 passed in 0.2s",
        review=review,
        metadata={
            "execution_mode": "single_agent",
            "execution_rationale": "bounded scope suitable for single agent",
            "leader_model": "deepseek-r1",
            "coding_model": "deepseek-v3",
            "review_model": "deepseek-r1",
            "trajectory_id": "traj-auth-101",
            "trajectory_event_count": "12",
            "model_calls": "3",
            "tool_calls": "8",
            "input_tokens": "4500",
            "output_tokens": "1200",
        },
    )
    change = ChangeRequestRef(
        repository=REPO,
        change_id="pr-55",
        title="implement auth cache",
        source_branch="feat/auth-cache",
        target_branch="main",
        state="open",
    )
    ci = CIRunRef(
        provider_id="mock",
        run_id="ci-888",
        repository=REPO,
        status="completed",
        conclusion="success",
        commit_sha="a1b2c3d4e5f67890",
    )
    verif = VerificationResult(
        accepted=True,
        summary="All tests passed and code reviewed.",
        evidence=("commit:a1b2c3d4e5f67890", "ci_run:ci-888"),
        outcome_status="verified_clean",
        task_success=True,
        runtime_clean_completion=True,
        evidence_completeness=True,
    )

    state = DeliveryState(
        task=task,
        phase=DeliveryPhase.VERIFIED,
        execution=execution,
        change_request=change,
        ci_run=ci,
        verification=verif,
    )
    stored = StoredDeliveryState(
        delivery_id="deliv-auth-101",
        version=4,
        state=state,
    )

    remediation_records = (
        RemediationRecord(
            delivery_id="deliv-auth-101",
            attempt=1,
            failure_kind=CIFailureKind.CODE,
            action=RemediationAction.PATCH,
            outcome=RemediationOutcome.COMPLETED,
            summary="fixed lint format error",
            previous_commit_sha="a0000000",
            resulting_commit_sha="a1b2c3d4e5f67890",
            status=RemediationStatus.COMPLETED,
        ),
    )

    report = DeliveryReportService.generate_report(stored, remediation_records)

    # 1. Verify JSON schema
    report_dict = report.to_dict()
    assert report_dict["delivery_id"] == "deliv-auth-101"
    assert report_dict["phase"] == "verified"
    assert report_dict["plan"]["mode"] == "single_agent"
    assert report_dict["execution"]["commit_sha"] == "a1b2c3d4e5f67890"
    assert report_dict["review"]["verdict"] == "approved"
    assert report_dict["verification"]["status"] == "verified_clean"
    assert report_dict["remediation"]["attempts"] == 1
    assert len(report_dict["remediation"]["history"]) == 1
    print("REPORT_JSON_STRUCTURE_OK")

    # 2. Verify Markdown report content
    md = report.to_markdown()
    assert "# DevOpsPilot Delivery Report: deliv-auth-101" in md
    assert "✅ VERIFIED CLEAN" in md
    assert "single_agent" in md
    assert "a1b2c3d4e5f67890" in md
    assert "APPROVED" in md
    assert "traj-auth-101" in md
    assert "Attempt #1" in md
    print("REPORT_MARKDOWN_CONTENT_OK")


def main() -> None:
    test_delivery_report_generation()
    print("ALL DELIVERY REPORT SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
