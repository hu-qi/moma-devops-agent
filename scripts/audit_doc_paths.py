#!/usr/bin/env python3
"""Audit Markdown documentation for broken relative links and stale repo paths.

R20: ensures all relative links in Markdown files resolve to existing files,
and all backtick-quoted repo paths (src/…, tests/…, experiments/…, etc.)
point to real locations in the repository.

Usage:
    python scripts/audit_doc_paths.py          # audit all docs
    python scripts/audit_doc_paths.py --fix    # print suggested fixes (no writes)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Markdown files to audit
MD_GLOBS = [
    "*.md",
    "docs/**/*.md",
]

# Regex: Markdown relative links  [text](path) — skip http/https/mailto/#anchors
RE_MD_LINK = re.compile(
    r'\[(?:[^\]]*)\]\((?!https?://|mailto:|#)([^)#\s]+?)(?:#[^)]*)?\)'
)

# Regex: backtick-quoted repo paths like `src/devopspilot/foo.py` or `tests/bar/`
RE_REPO_PATH = re.compile(
    r'`((?:src|tests|experiments|benchmarks|scripts|industry-packs|docs|\.github)/[^`\s]+)`'
)


def collect_md_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in MD_GLOBS:
        files.update(ROOT.glob(pattern))
    return sorted(files)


def audit_relative_links(md_file: Path) -> list[dict]:
    """Check that all relative links in a Markdown file resolve."""
    issues: list[dict] = []
    text = md_file.read_text(encoding="utf-8", errors="replace")
    base_dir = md_file.parent

    for lineno, line in enumerate(text.splitlines(), 1):
        for match in RE_MD_LINK.finditer(line):
            link_path = match.group(1)
            # Skip template/variable links
            if "{" in link_path or "<" in link_path:
                continue
            target = (base_dir / link_path).resolve()
            if not target.exists():
                issues.append({
                    "file": str(md_file.relative_to(ROOT)),
                    "line": lineno,
                    "type": "broken_link",
                    "path": link_path,
                    "resolved": str(target.relative_to(ROOT)) if target.is_relative_to(ROOT) else str(target),
                })
    return issues


def audit_repo_paths(md_file: Path) -> list[dict]:
    """Check that backtick-quoted repo paths exist."""
    issues: list[dict] = []
    text = md_file.read_text(encoding="utf-8", errors="replace")

    for lineno, line in enumerate(text.splitlines(), 1):
        for match in RE_REPO_PATH.finditer(line):
            repo_path = match.group(1).rstrip("/")
            # Strip trailing punctuation that leaked into the backtick
            repo_path = repo_path.rstrip(".,;:)")
            # Strip trailing :lineno or :lineno:col from file:line notations
            repo_path = re.sub(r":\d+(?::\d+)?$", "", repo_path)

            # Skip templates like docs/evidence/rc-<tag>/...
            if "<" in repo_path or ">" in repo_path or "{" in repo_path:
                continue

            # Support glob patterns like benchmarks/cases/*/fixture
            if "*" in repo_path:
                matches = list(ROOT.glob(repo_path))
                if not matches:
                    issues.append({
                        "file": str(md_file.relative_to(ROOT)),
                        "line": lineno,
                        "type": "stale_glob_path",
                        "path": repo_path,
                    })
                continue

            target = ROOT / repo_path
            if not target.exists():
                # Check if it's a directory reference (with trailing /)
                if not (ROOT / (repo_path + "/")).exists():
                    issues.append({
                        "file": str(md_file.relative_to(ROOT)),
                        "line": lineno,
                        "type": "stale_repo_path",
                        "path": repo_path,
                    })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Markdown docs for broken links and stale paths")
    parser.add_argument("--fix", action="store_true", help="Show suggested fixes (no actual writes)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    md_files = collect_md_files()
    all_issues: list[dict] = []

    for md_file in md_files:
        all_issues.extend(audit_relative_links(md_file))
        all_issues.extend(audit_repo_paths(md_file))

    if args.json:
        import json
        print(json.dumps({
            "files_checked": len(md_files),
            "issues": len(all_issues),
            "details": all_issues,
        }, ensure_ascii=False, indent=2))
        return 1 if all_issues else 0

    print(f"Checked {len(md_files)} Markdown files")
    if not all_issues:
        print("No broken links or stale paths found.")
    else:
        print(f"Found {len(all_issues)} issues:\n")
        for issue in all_issues:
            kind = issue["type"]
            print(f"  {issue['file']}:{issue['line']}  [{kind}]  {issue['path']}")

    if all_issues:
        print(f"\n{len(all_issues)} issue(s) found — exit 1")
        return 1

    print("\nAll documentation paths verified — exit 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
