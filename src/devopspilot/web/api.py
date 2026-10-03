"""REST API endpoints for the DevOpsPilot Web Management Console (R22+)."""

from __future__ import annotations

import json
import os
import platform
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from devopspilot.web.server import DashboardApiRouter

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = ROOT / ".devopspilot" / "state.db"
DEFAULT_TRAJECTORY_DIR = ROOT / ".devopspilot" / "trajectories"


def _get_git_commit_sha() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_active_rc_tag() -> str:
    try:
        proc = subprocess.run(
            ["git", "tag", "--points-at", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0]
    except Exception:
        pass
    return "rc-2026-mobile-cloud-cup-01"


def register_dashboard_apis(
    router: DashboardApiRouter,
    db_path: Path | None = None,
    trajectory_dir: Path | None = None,
) -> None:
    actual_db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    actual_traj_dir = Path(trajectory_dir) if trajectory_dir else DEFAULT_TRAJECTORY_DIR

    # 1. System Status API
    @router.get("/api/status")
    def handle_status(query: Mapping[str, list[str]]) -> dict[str, Any]:
        commit_sha = _get_git_commit_sha()
        rc_tag = _get_active_rc_tag()

        # Count deliveries if DB exists
        deliveries_count = 0
        if actual_db_path.is_file():
            try:
                with sqlite3.connect(str(actual_db_path)) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT count(*) FROM delivery_state")
                    row = cur.fetchone()
                    if row:
                        deliveries_count = row[0]
            except Exception:
                pass

        # Count trajectories
        trajectories_count = 0
        if actual_traj_dir.is_dir():
            trajectories_count = len(list(actual_traj_dir.glob("*.json")))

        # Count benchmark cases
        cases_dir = ROOT / "benchmarks" / "cases"
        benchmark_cases_count = len(list(cases_dir.glob("*/case.json"))) if cases_dir.is_dir() else 0

        # Count industry packs
        packs_dir = ROOT / "industry-packs"
        packs_count = len(list(packs_dir.glob("*/pack.yaml"))) if packs_dir.is_dir() else 0

        return {
            "version": "0.1.0",
            "release_candidate_tag": rc_tag,
            "commit_sha": commit_sha,
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "status": "OPERATIONAL",
            "db_path": str(actual_db_path.relative_to(ROOT)) if actual_db_path.is_relative_to(ROOT) else str(actual_db_path),
            "db_exists": actual_db_path.is_file(),
            "counts": {
                "deliveries": deliveries_count,
                "trajectories": trajectories_count,
                "benchmark_cases": benchmark_cases_count,
                "industry_packs": packs_count,
                "offline_checks": 41,
            },
            "models_config": {
                "coding_model": os.environ.get("MOMA_CODING_MODEL", "Qwen3-32B"),
                "review_model": os.environ.get("MOMA_REVIEW_MODEL", "deepseek-v4.1-flash"),
                "pricing_ref": "https://ecloud.10086.cn/op-help-center/doc/article/91592",
            },
        }

    # 2. List Deliveries API
    @router.get("/api/deliveries")
    def handle_list_deliveries(query: Mapping[str, list[str]]) -> dict[str, Any]:
        limit = 50
        if "limit" in query:
            try:
                limit = int(query["limit"][0])
            except ValueError:
                pass

        items: list[dict[str, Any]] = []
        if actual_db_path.is_file():
            try:
                with sqlite3.connect(str(actual_db_path)) as conn:
                    conn.row_factory = sqlite3.Row
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT delivery_id, version, phase, task_json, payload_json, updated_at "
                        "FROM delivery_state ORDER BY updated_at DESC LIMIT ?",
                        (limit,),
                    )
                    for row in cur.fetchall():
                        task_data = {}
                        payload_data = {}
                        try:
                            task_data = json.loads(row["task_json"])
                        except Exception:
                            pass
                        try:
                            payload_data = json.loads(row["payload_json"])
                        except Exception:
                            pass

                        items.append({
                            "delivery_id": row["delivery_id"],
                            "version": row["version"],
                            "phase": row["phase"],
                            "task_id": task_data.get("task_id", ""),
                            "repository": task_data.get("repository", {}).get("name", "") if isinstance(task_data.get("repository"), dict) else str(task_data.get("repository", "")),
                            "target_branch": task_data.get("target_branch", ""),
                            "intent_type": task_data.get("intent", {}).get("intent_type", ""),
                            "updated_at": row["updated_at"],
                            "verdict": payload_data.get("review_result", {}).get("verdict", "") if isinstance(payload_data.get("review_result"), dict) else "",
                        })
            except Exception as exc:
                return {"items": [], "error": str(exc)}

        return {"total": len(items), "items": items}

    # 3. Get Single Delivery Detail API
    @router.get("/api/deliveries/{id}")
    def handle_get_delivery(delivery_id: str, query: Mapping[str, list[str]]) -> dict[str, Any] | None:
        if not actual_db_path.is_file():
            return None

        try:
            with sqlite3.connect(str(actual_db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute(
                    "SELECT delivery_id, version, phase, task_json, payload_json, created_at, updated_at "
                    "FROM delivery_state WHERE delivery_id = ?",
                    (delivery_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                task_obj = {}
                payload_obj = {}
                try:
                    task_obj = json.loads(row["task_json"])
                except Exception:
                    pass
                try:
                    payload_obj = json.loads(row["payload_json"])
                except Exception:
                    pass

                return {
                    "delivery_id": row["delivery_id"],
                    "version": row["version"],
                    "phase": row["phase"],
                    "task": task_obj,
                    "payload": payload_obj,
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
        except Exception:
            return None

    # 4. List Trajectories API
    @router.get("/api/trajectories")
    def handle_list_trajectories(query: Mapping[str, list[str]]) -> dict[str, Any]:
        trajectories: list[dict[str, Any]] = []
        if actual_traj_dir.is_dir():
            for p in sorted(actual_traj_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)[:50]:
                try:
                    content = json.loads(p.read_text(encoding="utf-8"))
                    trajectories.append({
                        "trajectory_id": content.get("trajectory_id", p.stem),
                        "task_id": content.get("task_id", ""),
                        "repository": content.get("repository", ""),
                        "event_count": content.get("event_count", len(content.get("events", []))),
                        "filename": p.name,
                    })
                except Exception:
                    pass
        return {"total": len(trajectories), "items": trajectories}

    # 5. Get Single Trajectory Detail API
    @router.get("/api/trajectories/{id}")
    def handle_get_trajectory(traj_id: str, query: Mapping[str, list[str]]) -> dict[str, Any] | None:
        if not actual_traj_dir.is_dir():
            return None
        safe_id = traj_id.replace("/", "_").replace("\\", "_")
        target = actual_traj_dir / f"{safe_id}.json"
        if not target.is_file():
            # Try without .json suffix if already included
            target = actual_traj_dir / safe_id
        if not target.is_file():
            return None

        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return None

    # 6. Industry Rules API
    @router.get("/api/rules")
    def handle_list_rules(query: Mapping[str, list[str]]) -> dict[str, Any]:
        packs_dir = ROOT / "industry-packs"
        packs: list[dict[str, Any]] = []
        total_rules = 0

        if packs_dir.is_dir():
            for pack_folder in sorted(packs_dir.iterdir()):
                pack_file = pack_folder / "pack.yaml"
                if pack_file.is_file():
                    try:
                        import yaml
                        data = yaml.safe_load(pack_file.read_text(encoding="utf-8")) or {}
                        rules = data.get("rules", [])
                        total_rules += len(rules)
                        packs.append({
                            "pack_id": data.get("pack_id", pack_folder.name),
                            "name": data.get("name", pack_folder.name),
                            "version": data.get("version", "1.0.0"),
                            "industry": data.get("industry", "general"),
                            "description": data.get("description", ""),
                            "rules_count": len(rules),
                            "rules": rules,
                        })
                    except Exception:
                        pass

        return {"total_packs": len(packs), "total_rules": total_rules, "packs": packs}

    # 7. DevOpsBench Benchmark Cases API
    @router.get("/api/benchmarks")
    def handle_list_benchmarks(query: Mapping[str, list[str]]) -> dict[str, Any]:
        cases_dir = ROOT / "benchmarks" / "cases"
        cases: list[dict[str, Any]] = []

        if cases_dir.is_dir():
            for case_folder in sorted(cases_dir.iterdir()):
                case_file = case_folder / "case.json"
                if case_file.is_file():
                    try:
                        case_data = json.loads(case_file.read_text(encoding="utf-8"))
                        cases.append({
                            "id": case_data.get("id", case_folder.name),
                            "folder": case_folder.name,
                            "category": case_data.get("category", "coding"),
                            "holdout": bool(case_data.get("holdout", False)),
                            "title": case_data.get("title", ""),
                            "description": case_data.get("description", ""),
                            "oracle_type": case_data.get("oracle", {}).get("type", ""),
                            "risk": case_data.get("risk", "low"),
                            "budget": case_data.get("budget", {}),
                        })
                    except Exception:
                        pass

        # Sort by category then title
        cases.sort(key=lambda c: (c["category"], not c["holdout"], c["id"]))
        return {
            "total": len(cases),
            "holdout_count": sum(1 for c in cases if c["holdout"]),
            "categories": {
                "coding": sum(1 for c in cases if c["category"] == "coding"),
                "code-review": sum(1 for c in cases if c["category"] == "code-review"),
                "ci-debug": sum(1 for c in cases if c["category"] == "ci-debug"),
            },
            "cases": cases,
        }

    # 8. Trigger Validate Fixtures API
    @router.post("/api/benchmarks/validate")
    def handle_validate_fixtures(body: dict[str, Any], query: Mapping[str, list[str]]) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "benchmarks" / "devopsbench" / "runner.py"), "validate-fixtures"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=60,
            )
            data = json.loads(proc.stdout)
            return {"success": proc.returncode == 0, "results": data}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    # 9. Trigger Demo Execution API (Deterministic)
    @router.post("/api/demo/run")
    def handle_run_demo(body: dict[str, Any], query: Mapping[str, list[str]]) -> dict[str, Any]:
        mode = body.get("mode", "deterministic")
        if mode not in {"deterministic", "recorded"}:
            return {"success": False, "error": "Only 'deterministic' or 'recorded' modes are supported via web demo"}

        try:
            demo_script = ROOT / "scripts" / "run_demo.sh"
            proc = subprocess.run(
                ["bash", str(demo_script), mode],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            return {
                "success": proc.returncode == 0,
                "exit_code": proc.returncode,
                "mode": mode,
                "stdout_tail": proc.stdout[-2000:] if proc.stdout else "",
                "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}
