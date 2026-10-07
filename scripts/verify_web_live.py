#!/usr/bin/env python3
"""Read-only remote verification; never creates Issues, PRs or comments."""

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from devopspilot.cli.main import load_dotenv_if_present  # noqa: E402
from devopspilot.web.console import ConsoleService, sanitize  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=None)
    parser.add_argument("--chat-check", action="store_true")
    parser.add_argument("--output", default="docs/evidence/web-console-live.json")
    args = parser.parse_args()
    load_dotenv_if_present(ROOT / ".env")
    import os

    console = ConsoleService(
        Path(args.db or os.getenv("DEVOPSPILOT_DB_PATH", ".devopspilot/state.db"))
    )
    evidence = {
        "checked_at": time.time(),
        "kind": "current_code_read_only_remote",
        "remote_writes": 0,
        "projects": [],
    }
    for project in console.projects()["items"]:
        result = {"provider": project["provider"], "repo": project["repo"]}
        try:
            data = console.sync_project(project)
            result.update(
                status="success",
                issue_count=len(data["issues"]),
                ci_count=len(data.get("ci_runs", [])),
                synced_at=data["synced_at"],
            )
        except Exception as exc:
            result.update(status="failed", error=sanitize(str(exc)))
        evidence["projects"].append(result)
    if args.chat_check:
        try:
            result = console.chat(
                {
                    "message": "仅根据当前持久化摘要，回答有多少交付记录。没有记录则明确回答无记录。"
                }
            )
            item = result["item"]
            evidence["moma_inference"] = {
                "status": "success",
                "model": item["model"],
                "usage": item["usage"],
                "answer": item["answer"],
            }
        except Exception as exc:
            evidence["moma_inference"] = {
                "status": "failed",
                "error": sanitize(str(exc)),
            }
    evidence["runtime"] = {
        k: v for k, v in console.runtime().items() if k not in {"jobs", "channels"}
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(sanitize(evidence), ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(sanitize(evidence), ensure_ascii=False))
    return 0 if any(p["status"] == "success" for p in evidence["projects"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
