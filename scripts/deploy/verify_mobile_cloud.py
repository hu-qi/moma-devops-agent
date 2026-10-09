#!/usr/bin/env python3
"""Run on the instance; read remote data and call MoMA without SCM writes."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
from urllib.request import Request, urlopen


def request(base, route, body=None):
    payload = None if body is None else json.dumps(body).encode()
    req = Request(base + route, data=payload, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=150) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--output", default="/var/lib/devopspilot/cloud-acceptance.json")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    report = {"hostname": platform.node(), "platform": platform.platform()}
    report["source_hashes"] = {
        str(p): hashlib.sha256((root / p).read_bytes()).hexdigest()
        for p in ("src/devopspilot/web/console.html", "src/devopspilot/web/console.py")
    }
    report["status"] = request(args.base, "/api/status")
    report["runtime"] = request(args.base, "/api/runtime")
    synced = request(args.base, "/api/projects/sync", {"provider": "github", "repo": "hu-qi/moma-devops-agent"})
    report["project_sync"] = {
        key: synced.get(key) for key in ("id", "source", "synced_at", "error", "success")
    }
    report["project_sync"]["issue_count"] = len(synced.get("issues", []))
    report["project_sync"]["ci_run_count"] = len(synced.get("ci_runs", []))
    answer = request(args.base, "/api/chat", {"message": "当前云端有已完成交付的证据吗？仅按真实持久化摘要回答。"})
    report["chat"] = answer
    with urlopen(args.base + "/", timeout=10) as response:
        report["web"] = {"http_status": response.status, "contains_brand": b"DevOpsPilot" in response.read()}
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    valid = (
        report["runtime"]["moma_configured"]
        and report["runtime"]["openjiuwen_installed"]
        and report["project_sync"]["source"] == "remote_api"
        and answer.get("success") is True
        and report["web"]["contains_brand"]
    )
    print(json.dumps({"cloud_component_acceptance": bool(valid), "project": report["project_sync"], "chat_model": answer.get("item", {}).get("model"), "output": args.output}, ensure_ascii=False))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
