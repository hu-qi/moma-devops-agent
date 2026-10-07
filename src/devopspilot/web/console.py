"""Persistent local console: real SCM reads and explicit asynchronous Live jobs."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
SECRET_KEY = re.compile(r"(?:token|secret|password|api_key|authorization)$", re.I)


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: "[REDACTED]" if SECRET_KEY.search(k) else sanitize(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        for key, secret in os.environ.items():
            if SECRET_KEY.search(key) and len(secret) >= 8:
                value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?:ghp_|github_pat_)[A-Za-z0-9_]+", "[REDACTED]", value)
        value = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[REDACTED]@", value)
    return value


def project_key(provider: str, repo: str) -> str:
    if provider not in {"github", "atomgit", "cnb"}:
        raise ValueError("不支持的代码托管平台")
    if (
        not re.fullmatch(r"[\w.-]+/[\w./-]+", repo)
        or ".." in repo
        or repo.endswith("/")
    ):
        raise ValueError("仓库必须为 owner/repository")
    return f"{provider}:{repo}"


def pipeline(payload: dict, running: bool = False) -> list[dict]:
    execution = payload.get("execution") or {}
    review = execution.get("review") or {}
    ci = payload.get("ci_run") or {}
    verification = payload.get("verification") or {}
    phase = payload.get("phase", "")
    rejected = phase == "rejected" or review.get("verdict") in {"rejected", "REJECTED"}
    return [
        {
            "id": "vod",
            "name": "VOD · 需求接入",
            "status": "complete" if payload.get("task") else "pending",
            "evidence": "SCM Issue",
        },
        {
            "id": "issue",
            "name": "Issue · 任务规划",
            "status": "complete" if execution else "running" if running else "pending",
            "evidence": (payload.get("task") or {}).get("metadata", {}).get("mode", ""),
        },
        {
            "id": "coding",
            "name": "Coding · 编码",
            "status": "complete"
            if execution.get("commit_sha")
            else "running"
            if running and phase == "received"
            else "pending",
            "evidence": execution.get("commit_sha", ""),
        },
        {
            "id": "qa",
            "name": "QA · 独立审查",
            "status": "blocked"
            if rejected
            else "complete"
            if review.get("verdict", "").lower() == "approved"
            else "pending",
            "evidence": review.get("verdict", ""),
        },
        {
            "id": "sre",
            "name": "SRE · CI 与验收",
            "status": "complete"
            if phase == "verified"
            and verification.get("accepted") is True
            and verification.get("runtime_clean_completion") is True
            and verification.get("evidence_completeness") is True
            else "blocked"
            if ci.get("conclusion") in {"failure", "cancelled"} or phase == "rejected"
            else "running"
            if phase in {"ci-pending", "change-opened", "ci-passed"}
            else "pending",
            "evidence": ci.get("conclusion") or ci.get("status", ""),
        },
    ]


class ConsoleService:
    def __init__(self, db_path: Path, trajectory_dir: Path | None = None):
        self.db_path = Path(db_path).resolve()
        self.trajectory_dir = trajectory_dir or self.db_path.parent / "trajectories"
        self.console_db = self.db_path.with_name(self.db_path.stem + ".console.db")
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._processes: dict[str, subprocess.Popen] = {}
        self._cancelled: set[str] = set()
        self._scheduler: threading.Thread | None = None
        self.console_db.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project TEXT, issue TEXT, state TEXT, created REAL, updated REAL, payload TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS schedules (id TEXT PRIMARY KEY, payload TEXT)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS chats (id TEXT PRIMARY KEY, created REAL, payload TEXT)"
            )

    def connect(self):
        db = sqlite3.connect(self.console_db, timeout=20)
        db.row_factory = sqlite3.Row
        return db

    def start(self):
        # Interrupted jobs remain visible; restarting the server never repeats writes.
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state='interrupted', updated=? WHERE state IN ('queued','running')",
                (time.time(),),
            )
        self._scheduler = threading.Thread(target=self._schedule_loop, daemon=True)
        self._scheduler.start()

    def close(self):
        self._stop.set()
        with self._lock:
            for proc in self._processes.values():
                self._kill_process(proc)
        if self._scheduler:
            self._scheduler.join(timeout=2)

    def _states(self) -> list[dict]:
        if not self.db_path.is_file():
            return []
        with sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True) as db:
            db.row_factory = sqlite3.Row
            exists = db.execute(
                "SELECT name FROM sqlite_master WHERE name='delivery_state'"
            ).fetchone()
            if not exists:
                return []
            rows = db.execute(
                "SELECT delivery_id, version, payload FROM delivery_state ORDER BY rowid DESC"
            ).fetchall()
        result = []
        job_map = {j["id"]: j for j in self.jobs()}
        for row in rows:
            payload = json.loads(row["payload"])
            task = payload.get("task") or {}
            repo = task.get("repository") or {}
            work = task.get("work_item") or {}
            execution = payload.get("execution") or {}
            job = job_map.get(row["delivery_id"])
            elapsed = (
                max(
                    0,
                    (
                        time.time()
                        if job["state"] in {"running", "queued"}
                        else job["updated"]
                    )
                    - job["created"],
                )
                if job
                else None
            )
            result.append(
                {
                    "delivery_id": row["delivery_id"],
                    "version": row["version"],
                    "phase": payload.get("phase"),
                    "repository": repo.get("full_name", ""),
                    "provider": repo.get("provider_id", ""),
                    "task_id": work.get("item_id", ""),
                    "title": work.get("title", ""),
                    "created_at": job["created"] if job else None,
                    "updated_at": job["updated"] if job else None,
                    "elapsed_seconds": round(elapsed) if elapsed is not None else None,
                    "agent_models": {
                        k: execution.get("metadata", {}).get(k + "_model", "")
                        for k in ("leader", "coding", "review")
                    },
                    "author": work.get("author_id", ""),
                    "target_branch": task.get("target_branch", ""),
                    "verdict": (execution.get("review") or {}).get("verdict", ""),
                    "completed": payload.get("phase") == "verified"
                    and (payload.get("verification") or {}).get("accepted") is True
                    and (payload.get("verification") or {}).get(
                        "runtime_clean_completion"
                    )
                    is True
                    and (payload.get("verification") or {}).get("evidence_completeness")
                    is True,
                    "evidence_type": "simulated"
                    if repo.get("provider_id") == "mock"
                    else "persisted",
                    "payload": payload,
                }
            )
        return sanitize(result)

    def deliveries(self, project: str = "", search: str = "") -> dict:
        items = self._states()
        if project:
            items = [
                i for i in items if f"{i['provider']}:{i['repository']}" == project
            ]
        if search:
            items = [
                i
                for i in items
                if search.lower() in json.dumps(i, ensure_ascii=False).lower()
            ]
        return {
            "total": len(items),
            "items": [{k: v for k, v in i.items() if k != "payload"} for i in items],
        }

    def detail(self, delivery_id: str) -> dict | None:
        item = next(
            (i for i in self._states() if i["delivery_id"] == delivery_id), None
        )
        if not item:
            return None
        payload = item["payload"]
        jobs = [j for j in self.jobs() if j["id"] == delivery_id]
        running = bool(jobs and jobs[0]["state"] == "running")
        item["stages"] = pipeline(payload, running)
        if (
            jobs
            and jobs[0]["state"] in {"failed", "interrupted"}
            and not item["completed"]
        ):
            index = (
                4
                if payload.get("change_request")
                else 3
                if payload.get("execution")
                else 2
            )
            item["stages"][index]["status"] = "blocked"
            item["stages"][index]["evidence"] = jobs[0]["payload"].get("error") or (
                "执行中断"
                if jobs[0]["state"] == "interrupted"
                else "执行失败；查看后台日志"
            )
        item["task"] = payload.get("task")
        item["job"] = jobs[0] if jobs else None
        traj_id = (
            (payload.get("execution") or {}).get("metadata", {}).get("trajectory_id")
        )
        item["trajectory"] = None
        if traj_id:
            path = (
                self.trajectory_dir
                / (str(traj_id).replace("/", "_").replace("\\", "_") + ".json")
            ).resolve()
            if path.is_relative_to(self.trajectory_dir.resolve()) and path.is_file():
                item["trajectory"] = sanitize(json.loads(path.read_text()))
        return item

    def projects(self) -> dict:
        with self.connect() as db:
            projects = {
                r["id"]: json.loads(r["payload"])
                for r in db.execute("SELECT * FROM projects")
            }
        configured = []
        github_repo = os.getenv("GITHUB_REPOSITORY", "")
        if github_repo:
            configured.append(("github", github_repo))
        for env, provider in (
            ("DEVOPSPILOT_URL", "atomgit"),
            ("ATOMGIT_REPOSITORY", "atomgit"),
            ("CNB_REPOSITORY", "cnb"),
        ):
            value = os.getenv(env, "")
            if value:
                repo = (
                    urlparse(value).path.strip("/").removesuffix(".git")
                    if "://" in value
                    else value
                )
                configured.append((provider, repo))
        for item in self._states():
            if item["provider"] in {"github", "atomgit", "cnb"}:
                configured.append((item["provider"], item["repository"]))
        for provider, repo in configured:
            key = project_key(provider, repo)
            projects.setdefault(
                key,
                {
                    "id": key,
                    "provider": provider,
                    "repo": repo,
                    "source": "configured",
                    "issues": [],
                    "synced_at": None,
                },
            )
        return {"items": sanitize(list(projects.values()))}

    def add_project(self, body: dict) -> dict:
        provider, repo = (
            str(body.get("provider", "github")),
            str(body.get("repo", "")).strip(),
        )
        key = project_key(provider, repo)
        item = {
            "id": key,
            "provider": provider,
            "repo": repo,
            "source": "operator",
            "issues": [],
            "synced_at": None,
        }
        with self.connect() as db:
            existing = db.execute(
                "SELECT payload FROM projects WHERE id=?", (key,)
            ).fetchone()
            if existing:
                item = json.loads(existing["payload"])
            item["trusted_config"] = {
                k: str(body[k]).strip()
                for k in (
                    "test_command",
                    "allowed_paths",
                    "forbidden_paths",
                    "required_checks",
                )
                if k in body
            }
            db.execute(
                "INSERT OR REPLACE INTO projects VALUES (?,?)", (key, json.dumps(item))
            )
        return item

    def sync_project(self, body: dict) -> dict:
        provider, repo = body.get("provider", "github"), str(body.get("repo", ""))
        key = project_key(provider, repo)

        async def fetch():
            if provider == "github":
                from devopspilot.adapters.github.client import GitHubHTTPClient

                client = GitHubHTTPClient(token=os.environ.get("GITHUB_TOKEN", ""))
            elif provider == "atomgit":
                from devopspilot.adapters.atomgit.client import AtomGitHTTPClient

                client = AtomGitHTTPClient(token=os.environ.get("ATOMGIT_TOKEN", ""))
            else:
                raise ValueError(
                    "CNB 自动交付尚未接入；可查看已有状态，不能伪造在线接入"
                )
            repository = await client.request_json("GET", f"/repos/{repo}")
            issues = await client.request_json(
                "GET", f"/repos/{repo}/issues", query={"state": "all", "per_page": 100}
            )
            runs = []
            if provider == "github":
                runs = (
                    await client.request_json(
                        "GET", f"/repos/{repo}/actions/runs", query={"per_page": 15}
                    )
                ).get("workflow_runs", [])
            return repository, issues, runs

        repository, issues, runs = asyncio.run(fetch())
        item = {
            "id": key,
            "provider": provider,
            "repo": repo,
            "source": "remote_api",
            "synced_at": time.time(),
            "default_branch": repository.get("default_branch", "main"),
            "url": repository.get("html_url"),
            "issues": [
                {
                    "id": str(i.get("number", i.get("id"))),
                    "title": i.get("title"),
                    "body": i.get("body", ""),
                    "state": i.get("state"),
                    "url": i.get("html_url"),
                    "author": (i.get("user") or {}).get("login", ""),
                    "updated_at": i.get("updated_at"),
                }
                for i in issues
                if "pull_request" not in i
            ],
            "ci_runs": [
                {
                    "id": str(r["id"]),
                    "name": r.get("name"),
                    "status": r.get("status"),
                    "conclusion": r.get("conclusion"),
                    "sha": r.get("head_sha"),
                    "url": r.get("html_url"),
                }
                for r in runs
            ],
        }
        item = sanitize(item)
        with self.connect() as db:
            existing = db.execute(
                "SELECT payload FROM projects WHERE id=?", (key,)
            ).fetchone()
            if existing:
                item["trusted_config"] = json.loads(existing["payload"]).get(
                    "trusted_config", {}
                )
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO projects VALUES (?,?)",
                (key, json.dumps(item, ensure_ascii=False)),
            )
        return item

    def jobs(self) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM jobs ORDER BY created DESC LIMIT 100"
            ).fetchall()
        return sanitize(
            [{**dict(r), "payload": json.loads(r["payload"])} for r in rows]
        )

    def submit(self, body: dict) -> dict:
        repo, issue = (
            str(body.get("repo", "")).strip(),
            str(body.get("issue", "")).strip(),
        )
        if not repo or not issue:
            raise ValueError("Both 'repo' and 'issue' are required fields")
        provider = str(body.get("provider", "github"))
        key = project_key(provider, repo)
        if provider not in {"github", "atomgit"}:
            raise ValueError("此平台不支持 Live 自动交付")
        if not os.environ.get("MOMA_API_KEY"):
            raise ValueError("MOMA_API_KEY 未配置，拒绝离线回退")
        if not os.environ.get(
            "GITHUB_TOKEN" if provider == "github" else "ATOMGIT_TOKEN"
        ):
            raise ValueError("SCM Token 未配置，拒绝离线回退")
        if not re.fullmatch(r"[\w-]+", issue):
            raise ValueError("Issue 编号无效")
        mode = body.get("mode", "single_agent")
        intent = body.get("intent", "")
        if mode not in {"single_agent", "agent_team"} or intent not in {
            "",
            "inquiry",
            "code_change",
        }:
            raise ValueError("执行模式或意图无效")
        action = body.get("action", "start")
        delivery_id = (
            str(body.get("delivery_id", ""))
            if action == "resume"
            else "web-" + uuid.uuid4().hex[:12]
        )
        if action not in {"start", "resume"} or (
            action == "resume" and not self.detail(delivery_id)
        ):
            raise ValueError("恢复任务不存在")
        with self._lock, self.connect() as db:
            active = db.execute(
                "SELECT id FROM jobs WHERE project=? AND issue=? AND state IN ('queued','running')",
                (key, issue),
            ).fetchone()
            if active:
                return {"success": True, "job_id": active["id"], "deduplicated": True}
            if action == "start":
                existing = next(
                    (
                        i
                        for i in self._states()
                        if i["provider"] == provider
                        and i["repository"] == repo
                        and i["task_id"] == issue
                    ),
                    None,
                )
                if existing:
                    return {
                        "success": True,
                        "job_id": existing["delivery_id"],
                        "deduplicated": True,
                    }
            now = time.time()
            project = next((p for p in self.projects()["items"] if p["id"] == key), {})
            config = {
                "trusted_config": project.get("trusted_config", {}),
                "repo": repo,
                "issue": issue,
                "provider": provider,
                "mode": mode,
                "intent": intent,
                "action": action,
                "log": "",
                "execution_exit_code": None,
            }
            db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?)",
                (delivery_id, key, issue, "queued", now, now, json.dumps(config)),
            )
        threading.Thread(
            target=self._run_job, args=(delivery_id, config), daemon=True
        ).start()
        return {"success": True, "job_id": delivery_id, "state": "queued"}

    @staticmethod
    def _kill_process(proc):
        if proc.poll() is None:
            try:
                if os.name == "posix":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
            except ProcessLookupError:
                pass

    def cancel_job(self, body):
        job_id = str(body.get("job_id", ""))
        with self._lock:
            proc = self._processes.get(job_id)
            if not proc:
                raise ValueError("任务未在当前服务中运行")
            self._cancelled.add(job_id)
            self._kill_process(proc)
        return {"success": True, "job_id": job_id, "state": "cancelled"}

    def _update_job(self, delivery_id, state, config):
        with self.connect() as db:
            db.execute(
                "UPDATE jobs SET state=?,updated=?,payload=? WHERE id=?",
                (
                    state,
                    time.time(),
                    json.dumps(sanitize(config), ensure_ascii=False),
                    delivery_id,
                ),
            )

    def _run_job(self, delivery_id: str, config: dict):
        self._update_job(delivery_id, "running", config)
        cmd = [
            sys.executable,
            "-u",
            "-m",
            "devopspilot.cli.main",
            config["action"],
            "--delivery-id",
            delivery_id,
            "--db",
            str(self.db_path),
            "--require-live",
        ]
        if config["action"] == "start":
            cmd += [
                "--provider",
                config["provider"],
                "--repo",
                config["repo"],
                "--issue",
                config["issue"],
                "--mode",
                config["mode"],
            ]
            if config["intent"]:
                cmd += ["--intent", config["intent"]]
        env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
        for name, value in config.get("trusted_config", {}).items():
            env["DEVOPSPILOT_" + name.upper()] = value
        # Limit signing isolation to this child process; never change global git.
        count = int(env.get("GIT_CONFIG_COUNT", "0"))
        env[f"GIT_CONFIG_KEY_{count}"] = "commit.gpgSign"
        env[f"GIT_CONFIG_VALUE_{count}"] = "false"
        env["GIT_CONFIG_COUNT"] = str(count + 1)
        try:
            with subprocess.Popen(
                cmd,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=os.name == "posix",
            ) as proc:
                with self._lock:
                    self._processes[delivery_id] = proc
                timer = threading.Timer(1800, self._kill_process, args=(proc,))
                timer.start()
                try:
                    for line in proc.stdout:
                        config["log"] = sanitize((config["log"] + line)[-30000:])
                        self._update_job(delivery_id, "running", config)
                    code = proc.wait()
                finally:
                    timer.cancel()
                    with self._lock:
                        self._processes.pop(delivery_id, None)
            config["execution_exit_code"] = code
            # Process completion is not delivery verification.
            terminal = (
                "cancelled"
                if delivery_id in self._cancelled
                else "interrupted"
                if self._stop.is_set()
                else "finished"
                if code == 0
                else "failed"
            )
            self._update_job(delivery_id, terminal, config)
        except Exception as exc:
            config["error"] = sanitize(str(exc))
            self._update_job(delivery_id, "failed", config)

    def schedules(self):
        with self.connect() as db:
            return [
                json.loads(r["payload"]) for r in db.execute("SELECT * FROM schedules")
            ]

    def save_schedule(self, body):
        if body.get("delete"):
            with self.connect() as db:
                db.execute("DELETE FROM schedules WHERE id=?", (str(body.get("id")),))
            return {"success": True}
        project_key(str(body.get("provider", "github")), str(body.get("repo", "")))
        if not str(body.get("issue", "")).strip():
            raise ValueError("Issue required")
        due = float(body.get("due", 0))
        if due <= time.time():
            raise ValueError("执行时间必须在未来")
        item = {
            k: body[k]
            for k in ("repo", "provider", "issue", "intent", "mode")
            if k in body
        }
        item.update(id=uuid.uuid4().hex[:12], due=due, state="scheduled")
        with self.connect() as db:
            db.execute(
                "INSERT INTO schedules VALUES (?,?)", (item["id"], json.dumps(item))
            )
        return {"success": True, "item": item}

    def _schedule_loop(self):
        while not self._stop.wait(2):
            for item in self.schedules():
                if item["state"] == "scheduled" and item["due"] <= time.time():
                    item["state"] = "dispatching"
                    with self.connect() as db:
                        db.execute(
                            "UPDATE schedules SET payload=? WHERE id=?",
                            (json.dumps(item), item["id"]),
                        )
                    try:
                        result = self.submit(item)
                        item.update(state="dispatched", job_id=result["job_id"])
                    except Exception as exc:
                        item.update(state="failed", error=sanitize(str(exc)))
                    with self.connect() as db:
                        db.execute(
                            "UPDATE schedules SET payload=? WHERE id=?",
                            (json.dumps(item), item["id"]),
                        )

    def knowledge(self, query=""):
        items = []
        for root in (ROOT / "PRD", ROOT / "docs" / "research", ROOT / "docs" / "setup"):
            for p in sorted(root.glob("*.md")):
                text = p.read_text(encoding="utf-8")
                if not query or query.lower() in text.lower():
                    items.append(
                        {
                            "path": str(p.relative_to(ROOT)),
                            "title": text.splitlines()[0].lstrip("# "),
                            "content": sanitize(text[:20000]),
                        }
                    )
        return {"items": items}

    def runtime(self):
        return {
            "moma_configured": bool(os.environ.get("MOMA_API_KEY")),
            "api_base": os.environ.get("MOMA_API_BASE", ""),
            "openjiuwen_installed": importlib.util.find_spec("openjiuwen") is not None,
            "models": {
                role: os.environ.get(env, "未配置")
                for role, env in (
                    ("vod", "MOMA_FAST_MODEL"),
                    ("issue", "MOMA_REASONING_MODEL"),
                    ("coding", "MOMA_CODING_MODEL"),
                    ("qa", "MOMA_REVIEW_MODEL"),
                    ("sre", "MOMA_REASONING_MODEL"),
                )
            },
            "providers": {
                p: {
                    "configured": bool(os.environ.get(e)),
                    "live_delivery_supported": p in {"github", "atomgit"},
                }
                for p, e in (
                    ("github", "GITHUB_TOKEN"),
                    ("atomgit", "ATOMGIT_TOKEN"),
                    ("cnb", "CNB_TOKEN"),
                )
            },
            "db": str(self.db_path.relative_to(ROOT))
            if self.db_path.is_relative_to(ROOT)
            else self.db_path.name,
            "jobs": self.jobs(),
            "channels": [
                {
                    "name": "SCM Issue / PR",
                    "status": "configured",
                    "description": "现有执行器提供 Issue/PR 交付反馈",
                },
                {
                    "name": "IM",
                    "status": "not_configured",
                    "description": "未提供 IM 平台与机器人配置",
                },
            ],
        }

    def chat_history(self):
        with self.connect() as db:
            return {
                "items": [
                    json.loads(r["payload"])
                    for r in db.execute(
                        "SELECT * FROM chats ORDER BY created DESC LIMIT 30"
                    )
                ]
            }

    def chat(self, body):
        from devopspilot.adapters.moma.client import MoMAClient

        message = str(body.get("message", "")).strip()
        if not message or len(message) > 6000:
            raise ValueError("问题须为 1–6000 字")
        model = os.getenv("MOMA_FAST_MODEL") or os.getenv("MOMA_MODEL")
        response = MoMAClient(
            timeout=float(os.getenv("MOMA_TIMEOUT", "120"))
        ).chat_completion(
            [
                {
                    "role": "system",
                    "content": "你是 DevOpsPilot 项目助手。仅根据提供的真实持久化交付摘要回答；无证据的结果明确说未知。你不能调用工具或执行外部操作。摘要："
                    + json.dumps(
                        self.deliveries(body.get("project", "")), ensure_ascii=False
                    ),
                },
                {"role": "user", "content": message},
            ],
            model=model,
            max_tokens=1500,
        )
        item = sanitize(
            {
                "id": uuid.uuid4().hex,
                "message": message,
                "answer": response["choices"][0]["message"]["content"],
                "model": model,
                "usage": response.get("usage", {}),
                "created": time.time(),
            }
        )
        with self.connect() as db:
            db.execute(
                "INSERT INTO chats VALUES (?,?,?)",
                (item["id"], item["created"], json.dumps(item, ensure_ascii=False)),
            )
        return {"success": True, "item": item}
