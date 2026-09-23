"""Live DevOpsBench A/B for build-debug Skill evolution candidate."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from devopspilot.adapters.openjiuwen import (
    OpenJiuwenSkillEvolutionProvider,
    OpenJiuwenTaskExecutor,
    materialize_skill_experience_candidate,
)
from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    BenchmarkObservation,
    EvolutionRequest,
    EvolutionSignalEvidence,
)
from devopspilot.contracts.execution import ExecutionWorkspace
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.evolution import EvolutionEngine


ROOT = Path(__file__).resolve().parents[2]
CASE_ID = "ci.github_actions.working_directory.001"
CASE_DIR = ROOT / "benchmarks" / "cases" / "ci-python-wrong-working-directory"
FIXTURE = CASE_DIR / "fixture"
PRODUCTION_SKILLS = ROOT / "skills"
ARTIFACT_DIR = ROOT / "artifacts"


def run(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


def build_request() -> EvolutionRequest:
    base = ArtifactVersion(
        artifact_id="skill.build-debug.experience",
        kind=ArtifactKind.SKILL_EXPERIENCE,
        version="1.0.0",
        content=json.dumps(
            {
                "format": "devopspilot.skill-experience/v1",
                "skill_name": "build-debug",
                "records": [],
            },
            sort_keys=True,
        ),
        metadata={"skill_name": "build-debug"},
    )
    trajectory_id = f"devopsbench:{CASE_ID}:baseline"
    return EvolutionRequest(
        request_id="build-debug-working-directory-ablation-v1",
        base_artifact=base,
        objective=(
            "Improve build-debug so an agent verifies the CI command execution "
            "directory and workflow working-directory before changing code, "
            "dependencies, or blindly retrying a failed build."
        ),
        source_trajectory_ids=(trajectory_id,),
        evaluation_cases=(CASE_ID,),
        signals=(
            EvolutionSignalEvidence(
                signal_type="execution_failure",
                section="Troubleshooting",
                excerpt=(
                    "The GitHub Actions test step executes from a nonexistent "
                    "backend directory while the service lives under service/. "
                    "The repair should be based on workflow execution context "
                    "and repository layout, not on changing application code "
                    "or dependencies."
                ),
                source="devopsbench",
                trajectory_id=trajectory_id,
                tool_name="ci-log",
                metadata={
                    "case_id": CASE_ID,
                    "failure_class": "wrong-working-directory",
                },
            ),
        ),
    )


class BenchmarkWorkspaceProvider:
    def __init__(self, *, skills_root: Path, variant: str) -> None:
        self.skills_root = skills_root
        self.variant = variant
        self.workspace: Path | None = None

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        workspace = Path(
            tempfile.mkdtemp(prefix=f"devopspilot_skill_ab_{self.variant}_")
        )
        shutil.copytree(FIXTURE, workspace, dirs_exist_ok=True)

        run("git", "init", cwd=workspace)
        run("git", "config", "user.name", "DevOpsBench", cwd=workspace)
        run("git", "config", "user.email", "devopsbench@local", cwd=workspace)
        run("git", "add", "-A", cwd=workspace)
        run("git", "commit", "-m", "fixture: failing CI workflow", cwd=workspace)
        source_branch = f"devopspilot/{self.variant}-working-directory"
        run("git", "checkout", "-b", source_branch, cwd=workspace)

        self.workspace = workspace
        return ExecutionWorkspace(
            path=workspace,
            source_branch=source_branch,
            base_commit=run("git", "rev-parse", "HEAD", cwd=workspace),
            metadata={
                "allowed_paths": ".github/workflows/ci.yml",
                "forbidden_paths": "verify_ci.py,service/test_app.py",
                "max_changed_files": "1",
                "test_command": "python verify_ci.py",
                "skills_dir": str(self.skills_root),
                "enabled_skills": "build-debug",
                "skill_mode": "all",
            },
        )

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        # Preserve the candidate workspace for deterministic post-run oracle
        # evaluation even if the runtime raises.
        return None


def benchmark_eval(workspace: Path, *, variant: str) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "python",
            str(ROOT / "benchmarks" / "devopsbench" / "runner.py"),
            "evaluate",
            "--case",
            CASE_ID,
            "--workspace",
            str(workspace),
            "--variant",
            variant,
            "--run-id",
            f"skill-evolution-{variant}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if not completed.stdout.strip():
        raise RuntimeError(
            f"DevOpsBench produced no JSON for {variant}: "
            f"{completed.stderr[-4000:]}"
        )
    return json.loads(completed.stdout)


async def run_variant(
    *,
    variant: str,
    skills_root: Path,
    task: DeliveryTask,
) -> tuple[BenchmarkObservation, dict[str, Any]]:
    provider = BenchmarkWorkspaceProvider(
        skills_root=skills_root,
        variant=variant,
    )
    executor = OpenJiuwenTaskExecutor(
        provider,
        max_iterations=20,
        completion_timeout=120.0,
    )

    started = time.perf_counter()
    execution = None
    execution_error = ""
    try:
        execution = await executor.execute(task)
    except Exception as exc:
        execution_error = f"{type(exc).__name__}: {exc}"
    duration_ms = int((time.perf_counter() - started) * 1000)

    if provider.workspace is None:
        raise RuntimeError(f"{variant} never created an evaluation workspace")

    report = benchmark_eval(provider.workspace, variant=variant)
    metadata = dict(execution.metadata) if execution is not None else {}

    observation = BenchmarkObservation(
        case_id=CASE_ID,
        task_success=bool(report["task_success"]),
        regression_count=int(report.get("regression_count", 0)),
        duration_ms=duration_ms,
        tool_calls=int(metadata.get("tool_calls", "0") or 0),
        input_tokens=int(metadata.get("input_tokens", "0") or 0),
        output_tokens=int(metadata.get("output_tokens", "0") or 0),
        runtime_clean_completion=(
            metadata.get("runtime_degraded") == "false"
            if execution is not None
            else None
        ),
    )

    detail = {
        "variant": variant,
        "task_success": observation.task_success,
        "duration_ms": duration_ms,
        "model_calls": int(metadata.get("model_calls", "0") or 0),
        "tool_calls": observation.tool_calls,
        "skill_tool_calls": int(metadata.get("skill_tool_calls", "0") or 0),
        "input_tokens": observation.input_tokens,
        "output_tokens": observation.output_tokens,
        "runtime_clean_completion": observation.runtime_clean_completion,
        "runtime_degraded": metadata.get("runtime_degraded"),
        "trajectory_id": metadata.get("trajectory_id"),
        "commit_sha": execution.commit_sha if execution is not None else None,
        "executor_error": execution_error or None,
        "oracle": report,
    }
    return observation, detail


async def main() -> None:
    production_log = PRODUCTION_SKILLS / "build-debug" / "evolutions.json"
    if production_log.exists():
        raise RuntimeError("Production build-debug evolution state must remain clean")

    request = build_request()
    engine = EvolutionEngine(
        provider=OpenJiuwenSkillEvolutionProvider(
            skills_root=PRODUCTION_SKILLS,
            language="en",
        )
    )
    candidate = await engine.propose(request)

    temp_root = Path(tempfile.mkdtemp(prefix="devopspilot_skill_ablation_"))
    baseline_skills = temp_root / "baseline-skills"
    candidate_skills = temp_root / "candidate-skills"
    shutil.copytree(PRODUCTION_SKILLS, baseline_skills)
    shutil.copytree(PRODUCTION_SKILLS, candidate_skills)

    record_ids = await materialize_skill_experience_candidate(
        candidate,
        target_skills_root=candidate_skills,
    )
    assert record_ids
    assert (candidate_skills / "build-debug" / "evolutions.json").is_file()
    assert not production_log.exists()

    repository = RepositoryRef(
        provider_id="devopsbench",
        repository_id=CASE_ID,
        full_name="devopsbench/ci-python-wrong-working-directory",
        default_branch="main",
    )
    work_item = WorkItemRef(
        repository=repository,
        item_id=CASE_ID,
        title="GitHub Actions wrong working directory",
        body=(
            "Diagnose why CI cannot run the test script and repair only the "
            "workflow configuration. Do not modify service code or verify_ci.py."
        ),
        labels=("ci-debug", "build-debug", "github-actions"),
    )
    task = DeliveryTask(
        repository=repository,
        work_item=work_item,
        target_branch="main",
        metadata={
            "task_type": "ci-debug",
            "risk_level": "low",
            "complexity": "2",
        },
    )

    baseline_obs, baseline_detail = await run_variant(
        variant="baseline-skill",
        skills_root=baseline_skills,
        task=task,
    )
    candidate_obs, candidate_detail = await run_variant(
        variant="candidate-skill",
        skills_root=candidate_skills,
        task=task,
    )

    evidence = engine.evaluate(
        request=request,
        candidate=candidate,
        baseline=(baseline_obs,),
        candidate_results=(candidate_obs,),
    )
    decision = engine.await_human_approval(
        candidate=candidate,
        evidence=evidence,
    )

    if evidence.gate_passed:
        assert decision.state is ApprovalState.PENDING_HUMAN
    else:
        assert decision.state is ApprovalState.REJECTED

    if production_log.exists():
        raise RuntimeError("A/B evaluation mutated production Skill state")

    result = {
        "case_id": CASE_ID,
        "candidate_id": candidate.candidate_id,
        "candidate_version": candidate.artifact.version,
        "candidate_summary": candidate.change_summary,
        "candidate_record_ids": list(record_ids),
        "baseline": baseline_detail,
        "candidate": candidate_detail,
        "gate": {
            "passed": evidence.gate_passed,
            "improved_metrics": list(evidence.improved_metrics),
            "regressions": list(evidence.regressions),
            "promotion_state": decision.state.value,
            "rollback_version": decision.rollback_version,
            "reason": decision.reason,
        },
        "production_skill_mutated": False,
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    output = ARTIFACT_DIR / "build-debug-evolution-ablation.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("SKILL_EVOLUTION_AB_BASELINE_COMPLETE")
    print("SKILL_EVOLUTION_AB_CANDIDATE_COMPLETE")
    print(
        "SKILL_EVOLUTION_AB_BASELINE="
        + json.dumps(baseline_detail, ensure_ascii=False, sort_keys=True)
    )
    print(
        "SKILL_EVOLUTION_AB_CANDIDATE="
        + json.dumps(candidate_detail, ensure_ascii=False, sort_keys=True)
    )
    print(f"SKILL_EVOLUTION_GATE_PASSED={str(evidence.gate_passed).lower()}")
    print(f"SKILL_EVOLUTION_PROMOTION_STATE={decision.state.value}")
    print(
        "SKILL_EVOLUTION_IMPROVED_METRICS="
        + ",".join(evidence.improved_metrics)
    )
    print(
        "SKILL_EVOLUTION_REGRESSIONS="
        + ",".join(evidence.regressions)
    )
    print("SKILL_EVOLUTION_PRODUCTION_MUTATION=false")


if __name__ == "__main__":
    asyncio.run(main())
