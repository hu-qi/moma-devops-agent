"""Smoke test for Single Agent First planner, ExecutionPlan serialization, and review enforcement."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.planning import ExecutionMode, ExecutionPlan
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.routing.execution_planner import SingleAgentFirstPlanner

REPO = RepositoryRef(provider_id="mock", repository_id="repo-1", full_name="org/repo", default_branch="main")


def test_simple_task_selects_single_agent() -> None:
    task = DeliveryTask(
        repository=REPO,
        work_item=WorkItemRef(repository=REPO, item_id="1", title="fix typo in docs"),
        target_branch="main",
        metadata={"complexity": "1", "risk_level": "low"},
    )
    planner = SingleAgentFirstPlanner()
    plan = planner.plan(task)

    assert plan.mode is ExecutionMode.SINGLE_AGENT
    assert "single" in plan.rationale.lower() and "agent" in plan.rationale.lower()
    assert plan.require_review is True
    print("SIMPLE_TASK_SINGLE_AGENT_OK")


def test_complex_task_selects_agent_team() -> None:
    task = DeliveryTask(
        repository=REPO,
        work_item=WorkItemRef(repository=REPO, item_id="2", title="major architectural refactor of storage engine"),
        target_branch="main",
        metadata={"complexity": "4", "risk_level": "high"},
    )
    planner = SingleAgentFirstPlanner()
    plan = planner.plan(task)

    assert plan.mode is ExecutionMode.AGENT_TEAM
    assert "multi-agent team" in plan.rationale.lower()
    assert plan.require_review is True
    print("COMPLEX_TASK_AGENT_TEAM_OK")


def test_explicit_override() -> None:
    task = DeliveryTask(
        repository=REPO,
        work_item=WorkItemRef(repository=REPO, item_id="3", title="simple fix"),
        target_branch="main",
        metadata={"complexity": "1", "execution_mode": "agent_team"},
    )
    planner = SingleAgentFirstPlanner()
    plan = planner.plan(task)

    assert plan.mode is ExecutionMode.AGENT_TEAM
    assert "override" in plan.rationale.lower()
    assert plan.require_review is True
    print("EXPLICIT_OVERRIDE_OK")


def test_plan_serialization_roundtrip() -> None:
    original = ExecutionPlan(
        mode=ExecutionMode.SINGLE_AGENT,
        rationale="fast fix",
        risk_level="low",
        context_summary="task 42",
        allowed_paths=("app.py",),
        forbidden_paths=("test_app.py",),
        test_command="pytest",
        budget_limit=2,
        require_review=True,
        metadata={"pack": "gov"},
    )
    json_str = original.to_json()
    loaded = ExecutionPlan.from_json(json_str)

    assert loaded == original
    assert loaded.mode is ExecutionMode.SINGLE_AGENT
    assert loaded.require_review is True
    assert loaded.allowed_paths == ("app.py",)
    print("EXECUTION_PLAN_SERIALIZATION_ROUNDTRIP_OK")


def main() -> None:
    test_simple_task_selects_single_agent()
    test_complex_task_selects_agent_team()
    test_explicit_override()
    test_plan_serialization_roundtrip()
    print("ALL EXECUTION PLANNER SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
