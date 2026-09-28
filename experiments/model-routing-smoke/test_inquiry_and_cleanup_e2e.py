"""End-to-end unit tests for inquiry direct response, output cleaning, and report service."""

import pytest
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    VerificationResult,
)
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.contracts.state import StoredDeliveryState
from devopspilot.orchestration.report_service import DeliveryReportService
from devopspilot.routing.intent import DecisionStatus, TaskIntentClassifier
from devopspilot.utils.model_text import (
    extract_json_payload,
    sanitize_file_content,
    strip_think_tags,
)


def test_full_inquiry_detection_and_report():
    # 1. Intent Classification (structured decision, policy v2)
    classifier = TaskIntentClassifier()
    decision = classifier.classify(
        title="[Test]列举当前有哪些文件",
        body="请罗列出项目当前已有的文件并说明其用途",
    )
    assert decision.is_inquiry
    assert decision.status is DecisionStatus.RESOLVED

    # 2. Simulated state in ANSWERED phase
    repo = RepositoryRef(
        provider_id="atomgit",
        repository_id="repo-test",
        full_name="huqi/DevOpsPilot-Test",
        default_branch="main",
    )
    work_item = WorkItemRef(
        repository=repo,
        item_id="2",
        title="[Test]列举当前有哪些文件",
        body="请罗列出项目当前已有的文件并说明其用途",
    )
    state = DeliveryState(
        task=DeliveryTask(
            repository=repo,
            work_item=work_item,
            target_branch="main",
            metadata={"intent": "inquiry", "mode": "direct_inquiry"},
        ),
        phase=DeliveryPhase.ANSWERED,
        execution=None,
        change_request=None,
        ci_run=None,
        verification=VerificationResult(
            accepted=True,
            summary="Direct inquiry answered via issue comment.",
            outcome_status="verified_clean",
        ),
    )
    stored = StoredDeliveryState(
        delivery_id="deliv-inquiry-001",
        version=1,
        state=state,
    )

    # 3. Verify Delivery Report formatting
    report = DeliveryReportService.generate_report(stored)
    md = report.to_markdown()

    assert "**Outcome**: 💬 ANSWERED" in md
    assert "**Phase**: `answered`" in md
    assert "- **Change Request**: None" in md
    assert "- **Commit SHA**: `none`" in md


def test_robust_model_output_cleaning_under_adversarial_think():
    adversarial_output = """<think>
User wants to list files.
I will create FILE_LIST.md.
Let's see what else: <thought>nested thought</thought>
</think>
{
  "summary": "Repository contains README.md",
  "files": [
    {
      "path": "README.md",
      "content": "# DevOpsPilot Test Repository\n\nInitial repository for AtomGit Live Provider Contract Verification."
    }
  ]
}"""
    parsed = extract_json_payload(adversarial_output)
    assert parsed["summary"] == "Repository contains README.md"
    assert len(parsed["files"]) == 1
    content = sanitize_file_content(parsed["files"][0]["content"])
    assert "<think>" not in content
    assert "Initial repository for AtomGit" in content
