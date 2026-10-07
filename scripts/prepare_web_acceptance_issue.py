#!/usr/bin/env python3
"""Create the user-authorized, bounded fixture Issue once; never merges PRs."""

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from devopspilot.cli.main import load_dotenv_if_present  # noqa: E402
from devopspilot.adapters.github.client import GitHubHTTPClient  # noqa: E402
from devopspilot.web.console import ConsoleService  # noqa: E402


def main():
    load_dotenv_if_present(ROOT / ".env")
    repo = os.environ["GITHUB_REPOSITORY"]
    evidence_file = ROOT / "docs/evidence/web-console-delivery.json"
    if evidence_file.exists():
        print(evidence_file.read_text())
        return
    body = {
        "title": "[DevOpsPilot Web Live Acceptance] Add fixture status metadata",
        "body": """## Controlled Web acceptance task

Implement a small, real fixture feature for DevOpsPilot Web delivery acceptance.

- Only modify `e2e/fixtures/github_delivery/app.py` and `e2e/fixtures/github_delivery/test_app.py`.
- Preserve `status() -> str` and its existing `fixed` result.
- Add `status_metadata() -> dict[str, str]` returning exactly `{"status": status(), "source": "devopspilot"}`.
- Extend `test_app.py` to assert the exact metadata result, preserving existing assertions.
- Run `cd e2e/fixtures/github_delivery && python test_app.py`.
- Produce a minimal patch, obtain independent Review, open one PR, and leave it unmerged.

This is a controlled Live acceptance fixture, not a claim of business production readiness.
""",
    }
    client = GitHubHTTPClient(token=os.environ["GITHUB_TOKEN"])
    issue = asyncio.run(client.request_json("POST", f"/repos/{repo}/issues", body=body))
    data = {
        "provider": "github",
        "repo": repo,
        "issue": str(issue["number"]),
        "issue_url": issue["html_url"],
        "kind": "current_code_controlled_live_fixture",
        "merged": False,
    }
    evidence_file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    console = ConsoleService(Path(os.getenv("DEVOPSPILOT_DB_PATH", "devopspilot.db")))
    console.add_project(
        {
            "provider": "github",
            "repo": repo,
            "test_command": "cd e2e/fixtures/github_delivery && python test_app.py",
            "allowed_paths": "e2e/fixtures/github_delivery/app.py,e2e/fixtures/github_delivery/test_app.py",
            "forbidden_paths": "src,tests,.github,pyproject.toml,requirements-lock.txt,requirements-runtime.txt",
            "required_checks": "",
        }
    )
    console.sync_project(data)
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
