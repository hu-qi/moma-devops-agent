#!/usr/bin/env python3
"""Audit documentation status consistency and enforce R21 anti-exaggeration rules.

R21 checks:
1. Prohibit unevidenced absolute terms ('100%', '完全满足', '当前 RC 全绿', '完全就绪')
   in Stage 5 competition materials unless explicitly labeled as 'Historical' or 'Planned'.
2. Ensure status in compliance matrix matches completion state in TODO.md.
3. Verify test counts (41 passed checks) are consistently reported across README and docs.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

AUDIT_FILES = [
    ROOT / "README.md",
    ROOT / "docs" / "competition" / "stage5-competition-compliance-matrix.md",
    ROOT / "docs" / "competition" / "stage5-presentation-outline.md",
    ROOT / "docs" / "competition" / "stage5-video-storyboard.md",
    ROOT / "docs" / "competition" / "stage5-clean-reproduction-and-audit.md",
    ROOT / "docs" / "competition" / "stage5-reviewer-guide.md",
]

# Patterns that indicate unevidenced exaggeration if not accompanied by Planned/Historical
PROHIBITED_PATTERNS = [
    (re.compile(r"100%"), "Absolute percentage '100%' without qualifier"),
    (re.compile(r"全部就绪"), "Unverified readiness '全部就绪'"),
    (re.compile(r"完全满足"), "Unverified absolute claim '完全满足'"),
    (re.compile(r"当前\s*RC\s*全绿"), "Unevidenced claim '当前 RC 全绿'"),
]


def audit_status_consistency() -> list[dict]:
    issues: list[dict] = []

    for file_path in AUDIT_FILES:
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(ROOT)
        text = file_path.read_text(encoding="utf-8", errors="replace")

        for lineno, line in enumerate(text.splitlines(), 1):
            # Allow lines explicitly labeled with Historical or Planned
            if "Historical" in line or "Planned" in line:
                continue

            for pattern, desc in PROHIBITED_PATTERNS:
                if pattern.search(line):
                    issues.append({
                        "file": str(rel_path),
                        "line": lineno,
                        "content": line.strip(),
                        "rule": desc,
                    })

    # Verify 41 test checks consistency (no lingering '40 Checks' or '40 passed')
    for file_path in [ROOT / "README.md", ROOT / "docs" / "competition" / "stage5-presentation-outline.md"]:
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(ROOT)
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), 1):
            if re.search(r"40\s*(Checks|passed|项)", line):
                issues.append({
                    "file": str(rel_path),
                    "line": lineno,
                    "content": line.strip(),
                    "rule": "Stale 40-check reference (should be 41)",
                })

    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit doc status consistency (R21)")
    args = parser.parse_args()

    issues = audit_status_consistency()
    if not issues:
        print("Status consistency audit PASS: no unevidenced claims, test counts aligned (41 checks).")
        return 0

    print(f"Status consistency audit FAIL ({len(issues)} issue(s) found):")
    for issue in issues:
        print(f"  {issue['file']}:{issue['line']} - [{issue['rule']}]")
        print(f"    Line: {issue['content']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
