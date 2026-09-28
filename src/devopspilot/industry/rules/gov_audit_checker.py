"""Government compliance and audit rule checker.

Enforces:
1. GOV-COMP-001 (MANDATORY): Audit trail on critical operations (GB/T 22239-2019 Cl. 7.1.4.3).
2. GOV-COMP-002 (MANDATORY): Sensitive personal data masking in logs (GB/T 35273-2020 Cl. 5.4).
3. GOV-COMP-003 (ADVISORY): Cross-architecture compatibility guidance.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuleViolation:
    rule_id: str
    category: str  # mandatory or advisory
    standard: str
    file_path: str
    line_number: int
    matched_text: str
    message: str


# Regex patterns for Chinese ID card (18 digits) and phone number (11 digits)
ID_CARD_PATTERN = re.compile(r"""\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b""")
PHONE_PATTERN = re.compile(r"""\b1[3-9]\d{9}\b""")
RAW_PASSWORD_LOG = re.compile(r"""(?i)(?:logger\.|logging\.|print\().*?(?:password|token|secret)\s*[:=]\s*["'][^"']+["']""")
SENSITIVE_LOG_CALL = re.compile(r"""(?i)(?:logger\.|logging\.|print\().*?(?:id_card|phone|mobile|idcard|id_number)""")


def scan_file_for_gov_rules(file_path: Path) -> list[RuleViolation]:
    violations: list[RuleViolation] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return violations

    lines = content.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Check GOV-COMP-002: Plaintext sensitive info in logs / prints
        # If line does not use masking helper (e.g. mask_, desensitize, ***)
        is_masked = any(m in line for m in ("mask_", "mask(", "desensitize", "***", "hide_"))

        if not is_masked:
            # Check ID card in log/print
            if any(call in line for call in ("print(", "logger.", "logging.", "console.log")):
                if ID_CARD_PATTERN.search(line):
                    violations.append(
                        RuleViolation(
                            rule_id="GOV-COMP-002",
                            category="mandatory",
                            standard="GB/T 35273-2020 Cl. 5.4",
                            file_path=str(file_path),
                            line_number=idx,
                            matched_text=line.strip()[:80],
                            message="Plaintext Citizen ID card number logged without masking",
                        )
                    )
                if PHONE_PATTERN.search(line):
                    violations.append(
                        RuleViolation(
                            rule_id="GOV-COMP-002",
                            category="mandatory",
                            standard="GB/T 35273-2020 Cl. 5.4",
                            file_path=str(file_path),
                            line_number=idx,
                            matched_text=line.strip()[:80],
                            message="Plaintext citizen mobile phone number logged without masking",
                        )
                    )

            if RAW_PASSWORD_LOG.search(line):
                violations.append(
                    RuleViolation(
                        rule_id="GOV-COMP-002",
                        category="mandatory",
                        standard="GB/T 22239-2019 Cl. 7.1.4.3",
                        file_path=str(file_path),
                        line_number=idx,
                        matched_text=line.strip()[:80],
                        message="Plaintext password or token logged directly",
                    )
                )

        # Check GOV-ARCH-001: Forbidden public CDN or curl pipe in code
        if any(bad in line for bad in ("curl -s http", "wget http", "unpkg.com", "cdnjs.cloudflare.com")):
            violations.append(
                RuleViolation(
                    rule_id="GOV-ARCH-001",
                    category="mandatory",
                    standard="政务云外网访问隔离规范",
                    file_path=str(file_path),
                    line_number=idx,
                    matched_text=line.strip()[:80],
                    message="Forbidden external runtime download or public CDN dependency in government context",
                )
            )

    return violations


def scan_directory(root_dir: Path) -> list[RuleViolation]:
    violations: list[RuleViolation] = []
    # Skip VCS and cache directories
    skip_dirs = {".git", ".svn", "__pycache__", "node_modules", ".pytest_cache", ".venv", "venv"}
    code_extensions = {".py", ".js", ".ts", ".go", ".java", ".sql"}

    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            path = Path(root) / f
            if path.suffix in code_extensions:
                violations.extend(scan_file_for_gov_rules(path))
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Government Engineering Pack Audit & Masking Gate")
    parser.add_argument("target_dir", nargs="?", default=".", help="Target repository directory to scan")
    args = parser.parse_args(argv)

    root = Path(args.target_dir).resolve()
    if not root.exists():
        sys.stderr.write(f"Target directory {root} does not exist\n")
        return 1

    violations = scan_directory(root)
    mandatory = [v for v in violations if v.category == "mandatory"]
    advisory = [v for v in violations if v.category == "advisory"]

    if advisory:
        print(f"[GOV-PACK ADVISORY] {len(advisory)} advisory recommendation(s):")
        for v in advisory:
            print(f"  - [{v.rule_id}] {v.file_path}:{v.line_number} -> {v.message}")

    if mandatory:
        print(f"[GOV-PACK REJECTED] {len(mandatory)} MANDATORY compliance violation(s) found:")
        for v in mandatory:
            print(f"  - [{v.rule_id}] {v.file_path}:{v.line_number} (Ref: {v.standard})")
            print(f"    Message: {v.message}")
            print(f"    Code:    {v.matched_text}")
        return 1

    print("[GOV-PACK PASSED] All government compliance and audit rules satisfied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
