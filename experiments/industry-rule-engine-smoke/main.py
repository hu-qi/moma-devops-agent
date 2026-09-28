"""Smoke test for executable industry compliance checkers (Government & Finance)."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.industry import RuleCategory
from devopspilot.industry.loader import load_pack_from_directory
from devopspilot.industry.rules.finance_precision_checker import main as finance_main
from devopspilot.industry.rules.gov_audit_checker import main as gov_main


def test_government_audit_checker() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_gov_rule_test_"))
    try:
        # 1. Negative test: Plaintext ID card and phone logged directly
        bad_file = tmp / "bad_gov_service.py"
        bad_file.write_text(
            """
import logging
logger = logging.getLogger(__name__)

def handle_citizen_request(id_card, phone):
    # Violation: Plaintext logging of citizen PII
    logger.info(f"Processing request for citizen: {id_card}, phone: 13812345678, id: 110101199003072345")
    return {"status": "ok"}
""",
            encoding="utf-8",
        )

        ret_bad = gov_main([str(tmp)])
        assert ret_bad == 1, "Should have failed due to unmasked citizen PII"
        print("GOV_CHECKER_NEGATIVE_CASE_BLOCKED_OK")

        # 2. Positive test: Properly masked logging
        bad_file.unlink()
        good_file = tmp / "good_gov_service.py"
        good_file.write_text(
            """
import logging
logger = logging.getLogger(__name__)

def mask_id(val):
    return val[:6] + "********" + val[-4:]

def handle_citizen_request(id_card, phone):
    masked_id = mask_id(id_card)
    logger.info(f"Processing citizen request with trace_id=t-100, masked_id={masked_id}")
    return {"status": "ok"}
""",
            encoding="utf-8",
        )

        ret_good = gov_main([str(tmp)])
        assert ret_good == 0, "Should have passed with masked PII"
        print("GOV_CHECKER_POSITIVE_CASE_PASSED_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_finance_precision_checker() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_fin_rule_test_"))
    try:
        # 1. Negative test: Float calculation and plaintext card PAN
        bad_file = tmp / "bad_payment.py"
        bad_file.write_text(
            """
import logging
logger = logging.getLogger(__name__)

def calculate_fee(price):
    # Violation: Binary float for currency
    amount = float(price) * 0.05
    # Violation: Plaintext PAN card log
    logger.info("Charging card: 6222021234567890123")
    return amount
""",
            encoding="utf-8",
        )

        ret_bad = finance_main([str(tmp)])
        assert ret_bad == 1, "Should have failed due to binary float & plaintext PAN"
        print("FINANCE_CHECKER_NEGATIVE_CASE_BLOCKED_OK")

        # 2. Positive test: Decimal calculation and masked PAN
        bad_file.unlink()
        good_file = tmp / "good_payment.py"
        good_file.write_text(
            """
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)

def calculate_fee(price_decimal):
    amount = price_decimal * Decimal("0.05")
    masked_card = "622202******0123"
    logger.info(f"Charging card {masked_card} with amount {amount}")
    return amount
""",
            encoding="utf-8",
        )

        ret_good = finance_main([str(tmp)])
        assert ret_good == 0, "Should have passed with Decimal and masked card"
        print("FINANCE_CHECKER_POSITIVE_CASE_PASSED_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_pack_metadata_and_authority_source() -> None:
    gov_pack = load_pack_from_directory(ROOT / "industry-packs" / "government")
    assert gov_pack.compliance_rules[0].category is RuleCategory.MANDATORY
    assert gov_pack.compliance_rules[0].authority_source is not None
    assert "GB/T 22239-2019" in gov_pack.compliance_rules[0].authority_source
    assert gov_pack.test_gates[0].command == "python -m devopspilot.industry.rules.gov_audit_checker ."

    fin_pack = load_pack_from_directory(ROOT / "industry-packs" / "finance")
    assert fin_pack.compliance_rules[0].category is RuleCategory.MANDATORY
    assert fin_pack.compliance_rules[0].authority_source is not None
    assert "PCI-DSS" in fin_pack.compliance_rules[0].authority_source
    assert fin_pack.test_gates[0].command == "python -m devopspilot.industry.rules.finance_precision_checker ."
    print("PACK_AUTHORITY_AND_GATES_VERIFIED_OK")


def main() -> None:
    test_government_audit_checker()
    test_finance_precision_checker()
    test_pack_metadata_and_authority_source()
    print("ALL INDUSTRY RULE ENGINE SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
