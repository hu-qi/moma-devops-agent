"""Shared live benchmark harness for AgentTeam role-model ablations.

This module is intentionally not auto-run on push. Expensive live-model
comparisons are triggered explicitly after the baseline executor is green.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from devopspilot.adapters.openjiuwen import OpenJiuwenTaskExecutor
from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.execution import ExecutionWorkspace
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef


ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = ROOT / "benchmarks" / "cases" / "coding-python-off-by-one"
FIXTURE = CASE_DIR / "fixture"


def run(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


class AblationWorkspaceProvider:
    def __init__(self, run_name: str) -> None:
        self.run_name = run_name

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        workspace = Path(
            tempfile.mkdtemp(prefix=f"devopspilot_ablation_{self.run_name}_")
        )
        shutil.copytree(FIXTURE, workspace, dirs_exist_ok=True)
        run("git", "init", cwd=workspace)
        run("git", "config", "user.name", "DevOpsBench", cwd=workspace)
        run("git", "config", "user.email", "devopsbench@local", cwd=workspace)
        run("git", "add", "-A", cwd=workspace)
        run("git", "commit", "-m", "fixture: initial failing state", cwd=workspace)
        branch = f"devopspilot/ablation-{self.run_name}"
        run("git", "checkout", "-b", branch, cwd=workspace)
        return ExecutionWorkspace(
            path=workspace,
            source_branch=branch,
            base_commit=run("git", "rev-parse", "HEAD", cwd=workspace),
            metadata={
                "allowed_paths": "range_sum.py",
                "forbidden_paths": "test_range_sum.py",
                "test_command": "python test_range_sum.py",
                "max_changed_files": "1",
            },
        )

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        return None


def task() -> DeliveryTask:
    repository = RepositoryRef(
        provider_id="devopsbench",
        repository_id="coding.python.off_by_one.001",
        full_name="devopsbench/coding-python-off-by-one",
        default_branch="main",
    )
    return DeliveryTask(
        repository=repository,
        work_item=WorkItemRef(
            repository=repository,
            item_id="coding.python.off_by_one.001",
            title="Python inclusive range off-by-one",
            body=(
                "Fix sum_to so it includes n while preserving the public API. "
                "Only range_sum.py may change. Do not modify test_range_sum.py."
            ),
            labels=("python", "off-by-one", "deterministic"),
        ),
        target_branch="main",
    )


def evaluate(workspace: Path, variant: str, run_id: str) -> dict:
    completed = subprocess.run(
        [
            "python",
            str(ROOT / "benchmarks" / "devopsbench" / "runner.py"),
            "evaluate",
            "--case",
            "coding.python.off_by_one.001",
            "--workspace",
            str(workspace),
            "--variant",
            variant,
            "--run-id",
            run_id,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    report = json.loads(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


async def execute(args: argparse.Namespace) -> dict:
    os.environ["MOMA_REASONING_MODEL"] = args.leader
    os.environ["MOMA_CODING_MODEL"] = args.coding
    os.environ["MOMA_REVIEW_MODEL"] = args.review

    name = f"{args.label}-r{args.repetition}"
    executor = OpenJiuwenTaskExecutor(
        AblationWorkspaceProvider(name),
        max_iterations=args.max_iterations,
        completion_timeout=args.timeout,
    )

    started = time.perf_counter()
    result = await executor.execute(task())
    duration_ms = int((time.perf_counter() - started) * 1000)
    workspace = Path(result.metadata["workspace_path"])
    report = evaluate(
        workspace,
        variant=args.label,
        run_id=name,
    )

    return {
        "label": args.label,
        "repetition": args.repetition,
        "leader_model": result.metadata.get("leader_model"),
        "coding_model": result.metadata.get("coding_model"),
        "review_model": result.metadata.get("review_model"),
        "duration_ms": duration_ms,
        "commit_sha": result.commit_sha,
        "changed_paths": result.metadata.get("changed_paths", "").split(","),
        "task_success": report["task_success"],
        "test_pass": report["test_pass"],
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True)
    p.add_argument("--leader", required=True)
    p.add_argument("--coding", required=True)
    p.add_argument("--review", required=True)
    p.add_argument("--repetition", type=int, default=1)
    p.add_argument("--max-iterations", type=int, default=24)
    p.add_argument("--timeout", type=float, default=480.0)
    return p


async def main() -> None:
    report = await execute(parser().parse_args())
    print("ROLE_ABLATION_RESULT=" + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
