"""Live OpenJiuwen TaskExecutor validation against DevOpsBench."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
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


class BenchmarkWorkspaceProvider:
    def __init__(self) -> None:
        self.workspace: Path | None = None

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        workspace = Path(tempfile.mkdtemp(prefix="devopspilot_executor_bench_"))
        shutil.copytree(FIXTURE, workspace, dirs_exist_ok=True)

        run("git", "init", cwd=workspace)
        run("git", "config", "user.name", "DevOpsBench", cwd=workspace)
        run("git", "config", "user.email", "devopsbench@local", cwd=workspace)
        run("git", "add", "-A", cwd=workspace)
        run("git", "commit", "-m", "fixture: initial failing state", cwd=workspace)
        run("git", "checkout", "-b", "devopspilot/bench-off-by-one", cwd=workspace)

        self.workspace = workspace
        return ExecutionWorkspace(
            path=workspace,
            source_branch="devopspilot/bench-off-by-one",
            base_commit=run("git", "rev-parse", "HEAD", cwd=workspace),
            metadata={
                "allowed_paths": "range_sum.py",
                "forbidden_paths": "test_range_sum.py",
                "test_command": "python test_range_sum.py",
                "max_changed_files": "1",
            },
        )

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        # Preserve the failing workspace until process exit for CI diagnostics.
        return None


def benchmark_eval(workspace: Path) -> dict:
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
            "moma-openjiuwen-agentteam",
            "--run-id",
            "executor-live-spike",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(
            f"DevOpsBench returned no JSON. stderr={completed.stderr[-4000:]}"
        )
    report = json.loads(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(
            "DevOpsBench evaluation failed:\n"
            + json.dumps(report, ensure_ascii=False, indent=2)
        )
    return report


async def main() -> None:
    provider = BenchmarkWorkspaceProvider()
    executor = OpenJiuwenTaskExecutor(
        provider,
        max_iterations=24,
        completion_timeout=180.0,
    )

    repository = RepositoryRef(
        provider_id="devopsbench",
        repository_id="coding.python.off_by_one.001",
        full_name="devopsbench/coding-python-off-by-one",
        default_branch="main",
    )
    task = DeliveryTask(
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

    result = await executor.execute(task)
    workspace = Path(result.metadata["workspace_path"])

    assert result.published is False
    assert result.commit_sha == run("git", "rev-parse", "HEAD", cwd=workspace)
    assert result.metadata.get("trajectory_id")
    assert int(result.metadata.get("trajectory_event_count", "0")) > 0
    assert int(result.metadata.get("model_calls", "0")) > 0
    assert int(result.metadata.get("tool_calls", "0")) > 0
    assert int(result.metadata.get("input_tokens", "0")) > 0
    assert result.metadata.get("runtime_degraded") in {"true", "false"}

    changed = run(
        "git", "diff", "--name-only", "HEAD^", "HEAD", cwd=workspace
    ).splitlines()
    assert changed == ["range_sum.py"], changed

    status = run("git", "status", "--porcelain", cwd=workspace)
    assert status == "", status

    report = benchmark_eval(workspace)
    assert report["task_success"] is True
    assert report["test_pass"] is True

    print("OPENJIUWEN_TRAJECTORY_CAPTURE_OK")
    print("OPENJIUWEN_TASK_EXECUTOR_OK")
    print("AGENTTEAM_CODE_CHANGE_OK")
    print("AGENTTEAM_REVIEW_GATE_OK")
    print("LOCAL_COMMIT_OK")
    print("DEVOPSBENCH_ORACLE_OK")
    print(json.dumps({
        "commit_sha": result.commit_sha,
        "changed_files": changed,
        "task_success": report["task_success"],
        "test_pass": report["test_pass"],
        "workspace": str(workspace),
        "leader_model": result.metadata.get("leader_model"),
        "coding_model": result.metadata.get("coding_model"),
        "review_model": result.metadata.get("review_model"),
        "model_router_names": result.metadata.get("model_router_names"),
        "trajectory_id": result.metadata.get("trajectory_id"),
        "trajectory_event_count": result.metadata.get("trajectory_event_count"),
        "model_calls": result.metadata.get("model_calls"),
        "tool_calls": result.metadata.get("tool_calls"),
        "input_tokens": result.metadata.get("input_tokens"),
        "output_tokens": result.metadata.get("output_tokens"),
        "capture_issues": result.metadata.get("capture_issues"),
        "runtime_degraded": result.metadata.get("runtime_degraded"),
        "runtime_degradation_reason": result.metadata.get("runtime_degradation_reason"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
