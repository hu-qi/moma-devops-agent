"""Smoke test for IndustryGateRunner: real candidate violation rejection, fix pass, timeout, and verifier integration."""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.industry import (
    ComplianceRule,
    IndustryEngineeringPack,
    IndustryGateBlockedError,
    IndustryTestGate,
    PackRef,
    RuleCategory,
    RuleSeverity,
)
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.contracts.review import ReviewResult, ReviewVerdict
from devopspilot.industry.gate_runner import IndustryGateRunner
from devopspilot.orchestration.verifier import (
    DeliveryOutcomeStatus,
    StandardDeliveryVerifier,
)

REPO = RepositoryRef(provider_id="mock", repository_id="repo-gate", full_name="org/gate-repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="1", title="test item")


def make_pack(gate_command: str, timeout: int = 30) -> IndustryEngineeringPack:
    return IndustryEngineeringPack(
        pack_id="gov-pack-test",
        industry="government",
        version="1.0.0",
        title="Gov Pack",
        description="Gov Pack Description",
        compliance_rules=(
            ComplianceRule(
                rule_id="GOV-002",
                name="PII Masking",
                description="Mask PII",
                severity=RuleSeverity.CRITICAL,
                category=RuleCategory.MANDATORY,
            ),
        ),
        test_gates=(
            IndustryTestGate(
                gate_id="GOV-GATE-AUDIT",
                name="Audit Log Gate",
                command=gate_command,
                timeout_seconds=timeout,
                required=True,
            ),
        ),
    )


async def test_gate_runner_lifecycle_and_verifier() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_gate_runner_test_"))
    try:
        runner = IndustryGateRunner()
        python_exec = sys.executable

        # 1. Real candidate violation: unmasked citizen ID logged
        bad_code = tmp / "service.py"
        bad_code.write_text(
            """
import logging
logger = logging.getLogger(__name__)

def handle():
    # Violation: Plaintext citizen ID in log
    logger.info("Citizen ID: 110101199003072345")
""",
            encoding="utf-8",
        )

        gov_checker_cmd = f"{python_exec} -m devopspilot.industry.rules.gov_audit_checker ."
        pack = make_pack(gov_checker_cmd)

        try:
            await runner.run_gates(pack, cwd=tmp, enforce_required=True)
            assert False, "Should have raised IndustryGateBlockedError on real candidate violation"
        except IndustryGateBlockedError as exc:
            assert "Audit Log Gate" in str(exc)
            print("GATE_RUNNER_VIOLATION_BLOCKED_OK")

        # 2. Fix passes: replace with masked code
        bad_code.write_text(
            """
import logging
logger = logging.getLogger(__name__)

def handle():
    masked = "110101********2345"
    logger.info(f"Citizen ID masked: {masked}")
""",
            encoding="utf-8",
        )

        results = await runner.run_gates(pack, cwd=tmp, enforce_required=True)
        assert len(results) == 1
        assert results[0].passed is True
        print("GATE_RUNNER_FIX_PASSED_OK")

        # 3. Introduce defect again -> fails again
        bad_code.write_text(
            """
import logging
logger = logging.getLogger(__name__)

def handle():
    # New defect introduced
    logger.info("Phone leaked: 13812345678")
""",
            encoding="utf-8",
        )
        try:
            await runner.run_gates(pack, cwd=tmp, enforce_required=True)
            assert False, "Should have failed on re-introduced defect"
        except IndustryGateBlockedError:
            print("GATE_RUNNER_REINTRODUCED_DEFECT_BLOCKED_OK")

        # 4. Timeout control: command hanging beyond timeout is killed and blocked
        hang_cmd = f"{python_exec} -c 'import time; time.sleep(10)'"
        hang_pack = make_pack(hang_cmd, timeout=1)
        try:
            await runner.run_gates(hang_pack, cwd=tmp, enforce_required=True)
            assert False, "Should have blocked on timeout"
        except IndustryGateBlockedError as exc:
            assert "timed out after 1" in str(exc)
            print("GATE_RUNNER_TIMEOUT_BLOCKED_OK")

        # 5. Integration with StandardDeliveryVerifier
        verifier = StandardDeliveryVerifier()
        task = DeliveryTask(
            repository=REPO,
            work_item=WORK_ITEM,
            target_branch="main",
            pack_ref=PackRef(pack_id="gov-pack", version="1.0", digest="a"*64, industry="gov"),
        )
        review = ReviewResult(
            reviewer_id="reviewer-1",
            verdict=ReviewVerdict.APPROVED,
            diff_digest="digest-123",
            summary="ok",
        )
        from devopspilot.contracts.providers import CIRunRef
        ci_run = CIRunRef(provider_id="mock", run_id="ci-1", repository=REPO, status="completed", conclusion="success", commit_sha="c1")

        # 5a. If industry_gates_passed is "false" -> verifier rejects
        exec_failed = ExecutionResult(
            source_branch="b",
            commit_sha="c1",
            summary="done",
            published=True,
            review=review,
            metadata={"industry_gates_passed": "false", "trajectory_id": "t1", "trajectory_event_count": "5"},
        )
        state_failed = DeliveryState(task=task, phase=DeliveryPhase.CI_PASSED, execution=exec_failed, ci_run=ci_run)
        v_res_failed = await verifier.verify(state_failed)
        assert v_res_failed.accepted is False
        assert v_res_failed.outcome_status == DeliveryOutcomeStatus.REJECTED
        assert "Industry compliance/audit gates failed" in v_res_failed.summary
        print("VERIFIER_INDUSTRY_GATE_FAILED_REJECTED_OK")

        # 5b. If industry_gates_passed is "true" -> verifier accepts
        exec_passed = ExecutionResult(
            source_branch="b",
            commit_sha="c1",
            summary="done",
            published=True,
            review=review,
            metadata={"industry_gates_passed": "true", "trajectory_id": "t1", "trajectory_event_count": "5"},
        )
        state_passed = DeliveryState(task=task, phase=DeliveryPhase.CI_PASSED, execution=exec_passed, ci_run=ci_run)
        v_res_passed = await verifier.verify(state_passed)
        assert v_res_passed.accepted is True
        assert v_res_passed.outcome_status == DeliveryOutcomeStatus.VERIFIED_CLEAN
        print("VERIFIER_INDUSTRY_GATE_PASSED_ACCEPTED_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def main() -> None:
    await test_gate_runner_lifecycle_and_verifier()
    print("ALL INDUSTRY GATE RUNNER SMOKE TESTS PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
