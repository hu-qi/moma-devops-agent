"""Smoke test for Industry Engineering Packs (Contracts, Loader, Registry, and Gate)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.industry import (
    ArchitectureConstraint,
    ComplianceRule,
    IndustryEngineeringPack,
    IndustryTestGate,
    ReviewChecklistItem,
    RuleSeverity,
)
from devopspilot.industry import (
    InMemoryIndustryPackRegistry,
    build_industry_context,
    load_pack_from_directory,
    load_pack_from_dict,
)


def test_contracts() -> None:
    pack = IndustryEngineeringPack(
        pack_id="test-pack",
        industry="finance",
        version="1.0.0",
        title="Finance Core Pack",
        description="Pack for financial services.",
        compliance_rules=(
            ComplianceRule(
                rule_id="FIN-001",
                name="PCI-DSS Card Masking",
                description="Mask PAN fields in logs.",
                severity=RuleSeverity.CRITICAL,
                standard="PCI-DSS v4.0",
            ),
        ),
        architecture_constraints=(
            ArchitectureConstraint(
                constraint_id="FIN-ARCH-001",
                name="Idempotent Transaction APIs",
                description="All debit/credit APIs must require idempotency_key.",
                allowed_patterns=("IdempotencyKey",),
            ),
        ),
        review_checklist=(
            ReviewChecklistItem(
                item_id="FIN-REV-001",
                category="Compliance",
                prompt="Is cardholder data encrypted at rest?",
                must_pass=True,
            ),
        ),
        test_gates=(
            IndustryTestGate(
                gate_id="FIN-GATE-IDEMPOTENCY",
                name="Idempotency Test",
                command="python -c 'print(\"Idempotency verified\")'",
                timeout_seconds=30,
            ),
        ),
    )
    assert pack.pack_id == "test-pack"
    assert pack.compliance_rules[0].severity == RuleSeverity.CRITICAL
    assert pack.test_gates[0].command.startswith("python -c")
    print("INDUSTRY_PACK_CONTRACT_OK")


def test_loader_and_registry() -> None:
    gov_dir = ROOT / "industry-packs" / "government"
    pack = load_pack_from_directory(gov_dir)
    assert pack.pack_id == "devopspilot-industry-government"
    assert pack.industry == "government"
    assert len(pack.compliance_rules) >= 3
    assert len(pack.architecture_constraints) >= 2
    assert len(pack.review_checklist) >= 3
    assert len(pack.test_gates) >= 1
    print("INDUSTRY_PACK_LOADER_DIRECTORY_OK")

    registry = InMemoryIndustryPackRegistry()
    registry.register_pack(pack)
    assert registry.get_pack("devopspilot-industry-government") is not None
    assert registry.get_pack("nonexistent") is None

    gov_packs = registry.list_packs(industry="government")
    assert len(gov_packs) == 1
    fin_packs = registry.list_packs(industry="finance")
    assert len(fin_packs) == 0
    all_packs = registry.list_packs()
    assert len(all_packs) == 1
    print("INDUSTRY_PACK_REGISTRY_OK")

    context = build_industry_context(pack)
    assert "政务行业软件工程底座规范包" in context
    assert "GB/T 22239-2019" in context
    assert "GOV-REV-001" in context or "明文密钥" in context
    print("INDUSTRY_PACK_CONTEXT_BUILD_OK")

    # Gate execution verification
    gate = pack.test_gates[0]
    proc = subprocess.run(
        gate.command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=gate.timeout_seconds,
    )
    assert proc.returncode == 0
    assert "Audit Gate Checked: PASS" in proc.stdout
    print("INDUSTRY_PACK_GATE_EXECUTION_OK")


def main() -> None:
    test_contracts()
    test_loader_and_registry()
    print("ALL INDUSTRY PACK SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
