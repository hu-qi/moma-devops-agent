"""Deterministic tests for delivery -> evolution opportunity mining."""

from __future__ import annotations

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
    VerificationResult,
)
from devopspilot.contracts.evolution import ArtifactKind, OpportunityPriority
from devopspilot.contracts.providers import (
    CIJobLog,
    CIRunRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.evolution import DeliveryEvolutionMiner


def base_task() -> DeliveryTask:
    repo = RepositoryRef(
        provider_id="github",
        repository_id="hu-qi/moma-devops-agent",
        full_name="hu-qi/moma-devops-agent",
        default_branch="main",
    )
    item = WorkItemRef(
        repository=repo,
        item_id="1",
        title="E2E fixture",
        body="Fix fixture",
    )
    return DeliveryTask(repository=repo, work_item=item, target_branch="main")


def main() -> None:
    miner = DeliveryEvolutionMiner()
    task = base_task()

    degraded = DeliveryState(
        task=task,
        phase=DeliveryPhase.VERIFIED,
        execution=ExecutionResult(
            source_branch="devopspilot/e2e-1",
            commit_sha="deadbeef",
            summary="correct patch",
            published=True,
            metadata={
                "trajectory_id": "live:e2e:1",
                "runtime_degraded": "true",
                "runtime_degradation_reason": "agentteam_timeout",
                "tool_calls": "14",
                "model_calls": "17",
            },
        ),
        verification=VerificationResult(
            accepted=True,
            summary="CI passed",
        ),
    )
    opportunities = miner.mine(degraded)
    assert len(opportunities) == 1
    team = opportunities[0]
    assert team.target_kind is ArtifactKind.TEAM_PATTERN
    assert team.priority is OpportunityPriority.HIGH
    assert team.signals[0].signal_type == "runtime_degradation"
    assert team.source_trajectory_ids == ("live:e2e:1",)

    failed_run = CIRunRef(
        provider_id="github-actions",
        run_id="100",
        repository=task.repository,
        status="completed",
        conclusion="failure",
        commit_sha="deadbeef",
    )
    failed = DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=ExecutionResult(
            source_branch="fix/ci",
            commit_sha="deadbeef",
            summary="attempted repair",
            published=True,
            metadata={
                "trajectory_id": "live:ci:100",
                "runtime_degraded": "false",
            },
        ),
        ci_run=failed_run,
        ci_logs=(
            CIJobLog(
                run=failed_run,
                job_id="test",
                job_name="pytest",
                content="ModuleNotFoundError: service.app",
            ),
        ),
    )
    opportunities = miner.mine(failed)
    assert len(opportunities) == 1
    skill = opportunities[0]
    assert skill.target_kind is ArtifactKind.SKILL_EXPERIENCE
    assert skill.metadata["skill_name"] == "build-debug"
    assert skill.signals[0].signal_type == "ci_failure"

    clean = DeliveryState(
        task=task,
        phase=DeliveryPhase.VERIFIED,
        execution=ExecutionResult(
            source_branch="fix/clean",
            commit_sha="cafebabe",
            summary="clean delivery",
            published=True,
            metadata={
                "trajectory_id": "live:clean:1",
                "runtime_degraded": "false",
                "tool_calls": "8",
                "model_calls": "6",
            },
        ),
        verification=VerificationResult(
            accepted=True,
            summary="verified",
        ),
    )
    opportunities = miner.mine(clean)
    assert len(opportunities) == 1
    tool = opportunities[0]
    assert tool.target_kind is ArtifactKind.TOOL_STRATEGY
    assert tool.priority is OpportunityPriority.LOW

    print("EVOLUTION_RUNTIME_TO_TEAM_PATTERN_OK")
    print("EVOLUTION_CI_FAILURE_TO_SKILL_OK")
    print("EVOLUTION_CLEAN_SUCCESS_TO_TOOL_STRATEGY_OK")
    print("EVOLUTION_SIGNAL_CLASSIFICATION_OK")


if __name__ == "__main__":
    main()
