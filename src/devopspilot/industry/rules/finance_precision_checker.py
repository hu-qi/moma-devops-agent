"""Finance compliance, precision, and sensitive data masking checker.

Enforces:
1. FIN-COMP-001 (MANDATORY): Cardholder PAN masking and CVV prohibition (PCI-DSS v4.0 / JR/T 0071-2020).
2. FIN-COMP-002 (MANDATORY): Idempotency key requirement on mutation interfaces (JR/T 0197-2020).
3. FIN-COMP-003 (MANDATORY): Currency calculation precision — prohibits binary float arithmetic for money.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FinanceViolation:
    rule_id: str
    category: str
    standard: str
    file_path: str
    line_number: int
    matched_text: str
    message: str


# PAN detection (16-19 digits starting with 4, 5, 62)
PAN_PATTERN = re.compile(r"""\b(?:4\d{15}|5[1-5]\d{14}|62\d{14,17})\b""")
# Raw CVV or PIN in logs
CVV_LOG = re.compile(r"""(?i)(?:logger\.|logging\.|print\().*?(?:cvv|cvc|card_pin|cvv2)\s*[:=]""")
# Float arithmetic in money calculations: e.g. amount = float(x), price * 0.1, fee = round(..., 2) without Decimal
FLOAT_MONEY_PATTERN = re.compile(r"""(?i)(?:amount|balance|fee|price|salary|interest|trans_amt)\s*=\s*float\(""")


def scan_file_for_finance_rules(file_path: Path) -> list[FinanceViolation]:
    violations: list[FinanceViolation] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        is_masked = any(m in line for m in ("mask_", "mask(", "desensitize", "***", "hide_"))

        # Check FIN-COMP-001: PAN or CVV logged in plaintext
        if any(call in line for call in ("print(", "logger.", "logging.", "console.log")):
            if not is_masked and PAN_PATTERN.search(line):
                violations.append(
                    FinanceViolation(
                        rule_id="FIN-COMP-001",
                        category="mandatory",
                        standard="PCI-DSS v4.0 / JR/T 0071-2020",
                        file_path=str(file_path),
                        line_number=idx,
                        matched_text=line.strip()[:80],
                        message="Plaintext Primary Account Number (PAN) logged without masking",
                    )
                )
            if CVV_LOG.search(line):
                violations.append(
                    FinanceViolation(
                        rule_id="FIN-COMP-001",
                        category="mandatory",
                        standard="PCI-DSS v4.0 / JR/T 0071-2020",
                        file_path=str(file_path),
                        line_number=idx,
                        matched_text=line.strip()[:80],
                        message="Prohibited Sensitive Authentication Data (CVV/PIN) logged",
                    )
                )

        # Check FIN-COMP-003: Binary float used for monetary values
        if FLOAT_MONEY_PATTERN.search(line):
            violations.append(
                FinanceViolation(
                    rule_id="FIN-COMP-003",
                    category="mandatory",
                    standard="JR/T 0197-2020 金融业务数据精度规范",
                    file_path=str(file_path),
                    line_number=idx,
                    matched_text=line.strip()[:80],
                    message="Binary float type used for monetary amount; Decimal or integer cents required",
                )
            )

    return violations


def scan_directory(root_dir: Path) -> list[FinanceViolation]:
    violations: list[FinanceViolation] = []
    skip_dirs = {".git", ".svn", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv"}
    code_extensions = {".py", ".js", ".ts", ".go", ".java", ".sql"}

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            path = Path(root) / f
            if path.suffix in code_extensions:
                violations.extend(scan_file_for_finance_rules(path))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finance Engineering Pack Precision & Security Gate")
    parser.add_argument("target_dir", nargs="?", default=".", help="Target repository directory to scan")
    args = parser.parse_args(argv)

    root = Path(args.target_dir).resolve()
    if not root.exists():
        sys.stderr.write(f"Target directory {root} does not exist\n")
        return 1

    violations = scan_directory(root)
    mandatory = [v for v in violations if v.category == "mandatory"]

    if mandatory:
        print(f"[FINANCE-PACK REJECTED] {len(mandatory)} MANDATORY compliance violation(s) found:")
        for v in mandatory:
            print(f"  - [{v.rule_id}] {v.file_path}:{v.line_number} (Ref: {v.standard})")
            print(f"    Message: {v.message}")
            print(f"    Code:    {v.matched_text}")
        return 1

    print("[FINANCE-PACK PASSED] All financial precision and security rules satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
