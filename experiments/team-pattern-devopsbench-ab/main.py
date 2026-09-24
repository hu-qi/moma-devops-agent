"""Live DevOpsBench A/B for a governed Team Pattern Swarm Skill candidate."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from devopspilot.adapters.jiuwenswarm import (
    JiuwenSwarmSkillCandidateProvider,
    materialize_swarm_skill_candidate,
)
from devopspilot.adapters.openjiuwen import OpenJiuwenTaskExecutor
from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    BenchmarkObservation,
    EvolutionRequest,
    TeamPatternCreationDecision,
    TeamPatternCreationProposal,
)
from devopspilot.contracts.execution import ExecutionWorkspace
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.evolution import EvolutionEngine, RegressionGate
from devopspilot.persistence.evolution_audit import SQLiteEvolutionAuditStore


ROOT = Path(__file__).resolve().parents[2]
CASE_ID = "coding.python.off_by_one.001"
CASE_DIR = ROOT / "benchmarks" / "cases" / "coding-python-off-by-one"
FIXTURE = CASE_DIR / "fixture"
ARTIFACT_DIR = ROOT / "artifacts"


def git(*args: str, cwd: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip()


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
            f"team-pattern-{variant}",
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


def proposal() -> TeamPatternCreationProposal:
    return TeamPatternCreationProposal(
        proposal_id="synthetic-team-pattern-ab",
        proposal_key="devopspilot-team-runtime-agentteam-timeout",
        reusable_guidance=(
            "Create a reusable DevOps delivery Team/Swarm Skill that defines "
            "Leader, Coding, and Review collaboration; explicit task dependency "
            "and completion criteria; bounded member shutdown/timeout handling; "
            "independent verification before delivery; and a deterministic "
            "handoff from member completion to Leader finalization."
        ),
        evidence=(
            "trajectory-a: task correct but AgentTeam stream timed out after Coding and Review completed.",
            "trajectory-b: GitHub delivery verified but AgentTeam stream timed out during finalization.",
        ),
        source_opportunity_ids=(
            "team-pattern:bench:agentteam_timeout",
            "team-pattern:github-e2e:agentteam_timeout",
        ),
        provider_id="openjiuwen-team-skill-create",
        approval_payload={"synthetic": True},
        production_write=False,
    )


class BenchmarkWorkspaceProvider:
    def __init__(
        self,
        *,
        variant: str,
        skills_root: Path | None = None,
        enabled_skill: str = "",
    ) -> None:
        self.variant = variant
        self.skills_root = skills_root
        self.enabled_skill = enabled_skill
        self.workspace: Path | None = None

    async def prepare(self, task: DeliveryTask) -> ExecutionWorkspace:
        workspace = Path(
            tempfile.mkdtemp(prefix=f"devopspilot_team_pattern_{self.variant}_")
        )
        shutil.copytree(FIXTURE, workspace, dirs_exist_ok=True)
        git("init", cwd=workspace)
        git("config", "user.name", "DevOpsBench", cwd=workspace)
        git("config", "user.email", "devopsbench@local", cwd=workspace)
        git("add", "-A", cwd=workspace)
        git("commit", "-m", "fixture: initial failing state", cwd=workspace)
        branch = f"devopspilot/team-pattern-{self.variant}"
        git("checkout", "-b", branch, cwd=workspace)

        metadata = {
            "allowed_paths": "range_sum.py",
            "forbidden_paths": "test_range_sum.py",
            "test_command": "python test_range_sum.py",
            "max_changed_files": "1",
            "execution_id": self.variant,
        }
        if self.skills_root is not None:
            metadata.update({
                "skills_dir": str(self.skills_root),
                "enabled_skills": self.enabled_skill,
                "skill_mode": "all",
            })

        self.workspace = workspace
        return ExecutionWorkspace(
            path=workspace,
            source_branch=branch,
            base_commit=git("rev-parse", "HEAD", cwd=workspace),
            metadata=metadata,
        )

    async def cleanup(self, workspace: ExecutionWorkspace) -> None:
        return None


async def run_variant(
    *,
    variant: str,
    task: DeliveryTask,
    skills_root: Path | None = None,
    enabled_skill: str = "",
) -> tuple[BenchmarkObservation, dict[str, Any]]:
    workspace_provider = BenchmarkWorkspaceProvider(
        variant=variant,
        skills_root=skills_root,
        enabled_skill=enabled_skill,
    )
    executor = OpenJiuwenTaskExecutor(
        workspace_provider,
        max_iterations=24,
        completion_timeout=180.0,
    )

    started = time.perf_counter()
    execution = None
    failure_metadata: dict[str, str] = {}
    execution_error = ""
    try:
        execution = await executor.execute(task)
    except Exception as exc:
        execution_error = f"{type(exc).__name__}: {exc}"
        failure_metadata = dict(getattr(exc, "metadata", {}) or {})
    duration_ms = int((time.perf_counter() - started) * 1000)

    if workspace_provider.workspace is None:
        raise RuntimeError(f"{variant} did not create an evaluation workspace")

    report = benchmark_eval(workspace_provider.workspace, variant=variant)
    metadata = (
        dict(execution.metadata)
        if execution is not None
        else failure_metadata
    )

    runtime_clean = None
    if metadata.get("runtime_degraded") in {"true", "false"}:
        runtime_clean = metadata["runtime_degraded"] == "false"

    observation = BenchmarkObservation(
        case_id=CASE_ID,
        task_success=bool(report["task_success"]),
        regression_count=int(report.get("regression_count", 0)),
        duration_ms=duration_ms,
        tool_calls=int(metadata.get("tool_calls", "0") or 0),
        input_tokens=int(metadata.get("input_tokens", "0") or 0),
        output_tokens=int(metadata.get("output_tokens", "0") or 0),
        runtime_clean_completion=runtime_clean,
    )
    detail = {
        "variant": variant,
        "task_success": observation.task_success,
        "test_pass": bool(report.get("test_pass")),
        "duration_ms": observation.duration_ms,
        "runtime_clean_completion": observation.runtime_clean_completion,
        "runtime_degraded": metadata.get("runtime_degraded"),
        "runtime_degradation_reason": metadata.get(
            "runtime_degradation_reason"
        ),
        "model_calls": int(metadata.get("model_calls", "0") or 0),
        "tool_calls": observation.tool_calls,
        "skill_tool_calls": int(metadata.get("skill_tool_calls", "0") or 0),
        "input_tokens": observation.input_tokens,
        "output_tokens": observation.output_tokens,
        "trajectory_id": metadata.get("trajectory_id"),
        "enabled_skills": metadata.get("enabled_skills"),
        "executor_error": execution_error or None,
        "oracle": report,
    }
    return observation, detail


async def main() -> None:
    creator_root = Path(os.environ["JIUWENSWARM_CREATOR_ROOT"]).resolve()
    creator_ref = os.environ["JIUWENSWARM_CREATOR_REF"].strip()

    staged_proposal = proposal()
    approval = TeamPatternCreationDecision(
        proposal_id=staged_proposal.proposal_id,
        state=ApprovalState.APPROVED,
        decided_by="synthetic-ab-ci",
        reason="Evaluate the sandbox Team Pattern candidate; not production approval.",
    )
    provider = JiuwenSwarmSkillCandidateProvider(
        creator_root=creator_root,
        creator_ref=creator_ref,
    )
    candidate = await provider.generate_candidate(staged_proposal, approval)

    temp_root = Path(tempfile.mkdtemp(prefix="devopspilot_team_pattern_ab_"))
    candidate_skills = temp_root / "candidate-skills"
    candidate_skills.mkdir()
    candidate_dir = await materialize_swarm_skill_candidate(
        candidate,
        target_root=candidate_skills,
    )
    candidate_name = candidate_dir.name

    repository = RepositoryRef(
        provider_id="devopsbench",
        repository_id=CASE_ID,
        full_name="devopsbench/coding-python-off-by-one",
        default_branch="main",
    )
    task = DeliveryTask(
        repository=repository,
        work_item=WorkItemRef(
            repository=repository,
            item_id=CASE_ID,
            title="Python inclusive range off-by-one",
            body=(
                "Fix sum_to so it includes n while preserving the public API. "
                "Only range_sum.py may change. Do not modify test_range_sum.py."
            ),
            labels=("python", "off-by-one", "deterministic"),
        ),
        target_branch="main",
        metadata={
            "task_type": "coding",
            "risk_level": "low",
            "complexity": "2",
        },
    )

    baseline_obs, baseline_detail = await run_variant(
        variant="baseline-team",
        task=task,
    )
    candidate_obs, candidate_detail = await run_variant(
        variant="candidate-swarm-skill",
        task=task,
        skills_root=candidate_skills,
        enabled_skill=candidate_name,
    )

    request = EvolutionRequest(
        request_id="team-pattern-agentteam-timeout-ab-v1",
        base_artifact=ArtifactVersion(
            artifact_id=candidate.base_artifact_id,
            kind=ArtifactKind.TEAM_PATTERN,
            version=candidate.base_version,
            content="Dynamic Leader -> Coding -> Review baseline without reusable Team Skill.",
        ),
        objective=(
            "Improve AgentTeam completion/termination behavior without "
            "regressing task correctness or deterministic verification."
        ),
        source_trajectory_ids=candidate.source_trajectory_ids,
        evaluation_cases=(CASE_ID,),
    )

    evidence = RegressionGate().evaluate(
        request=request,
        candidate=candidate,
        baseline=(baseline_obs,),
        candidate_results=(candidate_obs,),
    )
    decision = EvolutionEngine.await_human_approval(
        candidate=candidate,
        evidence=evidence,
    )
    assert decision.state in {
        ApprovalState.REJECTED,
        ApprovalState.PENDING_HUMAN,
    }

    ARTIFACT_DIR.mkdir(exist_ok=True)
    db_path = ARTIFACT_DIR / "team-pattern-ab-audit.sqlite3"
    if db_path.exists():
        db_path.unlink()
    audit = SQLiteEvolutionAuditStore(db_path)
    await audit.save_team_pattern_proposal(staged_proposal)
    await audit.append_team_pattern_creation_decision(approval)
    await audit.save_candidate(candidate)
    stored_evidence = await audit.append_evidence(evidence)
    stored_decision = await audit.append_decision(decision)

    result = {
        "case_id": CASE_ID,
        "proposal_id": staged_proposal.proposal_id,
        "candidate_id": candidate.candidate_id,
        "candidate_name": candidate_name,
        "candidate_version": candidate.artifact.version,
        "creator_ref": creator_ref,
        "baseline": baseline_detail,
        "candidate": candidate_detail,
        "gate": {
            "passed": evidence.gate_passed,
            "improved_metrics": list(evidence.improved_metrics),
            "regressions": list(evidence.regressions),
            "promotion_state": decision.state.value,
            "reason": decision.reason,
        },
        "audit": {
            "evidence_version": stored_evidence.version,
            "decision_version": stored_decision.version,
        },
        "production_write": False,
    }
    output = ARTIFACT_DIR / "team-pattern-devopsbench-ab.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print("TEAM_PATTERN_AB_BASELINE_COMPLETE")
    print("TEAM_PATTERN_AB_CANDIDATE_COMPLETE")
    print(
        "TEAM_PATTERN_AB_BASELINE="
        + json.dumps(baseline_detail, ensure_ascii=False, sort_keys=True)
    )
    print(
        "TEAM_PATTERN_AB_CANDIDATE="
        + json.dumps(candidate_detail, ensure_ascii=False, sort_keys=True)
    )
    print(f"TEAM_PATTERN_GATE_PASSED={str(evidence.gate_passed).lower()}")
    print(f"TEAM_PATTERN_PROMOTION_STATE={decision.state.value}")
    print(
        "TEAM_PATTERN_IMPROVED_METRICS="
        + ",".join(evidence.improved_metrics)
    )
    print(
        "TEAM_PATTERN_REGRESSIONS="
        + ",".join(evidence.regressions)
    )
    print("TEAM_PATTERN_PRODUCTION_WRITE=false")


if __name__ == "__main__":
    asyncio.run(main())
