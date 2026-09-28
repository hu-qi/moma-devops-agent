"""Smoke test for PackRef contracts, digest calculation, sqlite_state roundtrip, and configuration error handling."""

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
    ArchitectureConstraint,
    ComplianceRule,
    IndustryEngineeringPack,
    IndustryTestGate,
    PackConfigurationError,
    PackRef,
    RuleSeverity,
)
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.orchestration.delivery_loop import DeliveryLoop
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore

REPO = RepositoryRef(provider_id="mock", repository_id="repo-pack", full_name="org/pack-repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="1", title="test pack item")


def test_pack_ref_and_digest() -> None:
    pack = IndustryEngineeringPack(
        pack_id="gov-audit-v1",
        industry="government",
        version="1.0.0",
        title="Government Audit Pack",
        description="Pack for audit trail enforcement",
        compliance_rules=(
            ComplianceRule(
                rule_id="GOV-001",
                name="Audit Logging",
                description="All operations must record user_id and timestamp",
                severity=RuleSeverity.BLOCKER,
                standard="GB/T-22239",
            ),
        ),
        architecture_constraints=(
            ArchitectureConstraint(
                constraint_id="ARCH-01",
                name="No Direct Log Injection",
                description="Use structured logger",
                forbidden_patterns=("print(",),
            ),
        ),
        test_gates=(
            IndustryTestGate(
                gate_id="GATE-01",
                name="Audit Test Gate",
                command="pytest tests/test_audit.py",
                required=True,
            ),
        ),
    )

    digest = pack.compute_digest()
    assert len(digest) == 64
    ref = pack.pack_ref()

    assert ref.pack_id == "gov-audit-v1"
    assert ref.version == "1.0.0"
    assert ref.digest == digest
    assert ref.industry == "government"
    print("PACK_REF_DIGEST_OK")


def test_state_store_roundtrip_with_pack_ref() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_pack_state_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)

        pack_ref = PackRef(
            pack_id="fin-precision-v1",
            version="1.2.0",
            digest="a" * 64,
            industry="finance",
            metadata={"source": "verified"},
        )

        task = DeliveryTask(
            repository=REPO,
            work_item=WORK_ITEM,
            target_branch="main",
            pack_ref=pack_ref,
        )
        state = DeliveryState(task=task, phase=DeliveryPhase.RECEIVED)

        # 1. Save and reload
        asyncio.run(store.save("deliv-pack-001", state, expected_version=0))
        loaded = asyncio.run(store.load("deliv-pack-001"))

        assert loaded is not None
        assert loaded.state.task.pack_ref is not None
        assert loaded.state.task.pack_ref.pack_id == "fin-precision-v1"
        assert loaded.state.task.pack_ref.version == "1.2.0"
        assert loaded.state.task.pack_ref.digest == "a" * 64
        assert loaded.state.task.pack_ref.industry == "finance"
        print("STATE_STORE_PACK_REF_ROUNDTRIP_OK")

        # 2. Backward compatibility: load legacy state without pack_ref
        legacy_task = DeliveryTask(repository=REPO, work_item=WORK_ITEM, target_branch="main")
        legacy_state = DeliveryState(task=legacy_task, phase=DeliveryPhase.RECEIVED)
        asyncio.run(store.save("deliv-legacy-001", legacy_state, expected_version=0))
        loaded_legacy = asyncio.run(store.load("deliv-legacy-001"))

        assert loaded_legacy is not None
        assert loaded_legacy.state.task.pack_ref is None
        print("STATE_STORE_LEGACY_COMPAT_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_delivery_loop_prepare_pack_ref_validation() -> None:
    class DummySCM:
        async def get_repository(self, repo_id: str) -> RepositoryRef:
            return REPO

        async def get_work_item(self, repo: RepositoryRef, item_id: str) -> WorkItemRef:
            return WORK_ITEM

    loop = DeliveryLoop(scm=DummySCM(), ci=None, executor=None, verifier=None)  # type: ignore[arg-type]

    # 1. Valid pack_ref in metadata
    valid_pack_dict = {
        "pack_id": "gov-pack",
        "version": "1.0",
        "digest": "b" * 64,
        "industry": "gov",
    }
    state = asyncio.run(loop.prepare_task(
        repository_id="repo-pack",
        work_item_id="1",
        target_branch="main",
        task_metadata={"industry_pack": valid_pack_dict},  # type: ignore[dict-item]
    ))
    assert state.task.pack_ref is not None
    assert state.task.pack_ref.pack_id == "gov-pack"
    print("DELIVERY_LOOP_PREPARE_VALID_PACK_OK")

    # 2. Corrupted pack in metadata -> raises PackConfigurationError, no silent ignore!
    try:
        asyncio.run(loop.prepare_task(
            repository_id="repo-pack",
            work_item_id="1",
            target_branch="main",
            task_metadata={"industry_pack": "{corrupted json invalid"},
        ))
        assert False, "Should have raised PackConfigurationError"
    except PackConfigurationError as exc:
        assert "Invalid industry_pack configuration" in str(exc)
        print("DELIVERY_LOOP_PREPARE_CORRUPTED_PACK_RAISES_OK")


def main() -> None:
    test_pack_ref_and_digest()
    test_state_store_roundtrip_with_pack_ref()
    test_delivery_loop_prepare_pack_ref_validation()
    print("ALL INDUSTRY PACK CONTRACT SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
