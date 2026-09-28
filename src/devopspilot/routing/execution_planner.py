"""Single Agent First planner determining execution mode, model routing, and review requirements."""

from __future__ import annotations

from typing import Mapping

from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.model_intelligence import RiskLevel, TaskProfile, TaskType
from devopspilot.contracts.planning import ExecutionMode, ExecutionPlan
from devopspilot.routing.profiler import DeliveryTaskProfiler


class SingleAgentFirstPlanner:
    """Planner favoring lightweight Single Agent execution for low-complexity/low-risk tasks,

    while reserving multi-agent AgentTeam for complex or high-risk architectural tasks.
    Independent review is strictly enforced on BOTH branches.
    """

    def __init__(self, profiler: DeliveryTaskProfiler | None = None) -> None:
        self._profiler = profiler or DeliveryTaskProfiler()

    def plan(
        self,
        task: DeliveryTask,
        *,
        override_mode: ExecutionMode | str | None = None,
        override_risk: str | None = None,
    ) -> ExecutionPlan:
        metadata = dict(task.metadata)
        title = task.work_item.title.lower()
        body = task.work_item.body.lower()

        # 1. Check explicit override in arguments or task metadata
        explicit_mode_str = (
            str(override_mode)
            if override_mode is not None
            else metadata.get("execution_mode")
        )
        if explicit_mode_str:
            clean_mode = str(explicit_mode_str).lower().strip()
            if clean_mode in {ExecutionMode.SINGLE_AGENT.value, "single", "single_agent"}:
                return self._create_plan(
                    task,
                    mode=ExecutionMode.SINGLE_AGENT,
                    rationale="Explicit user override selected single_agent mode",
                    risk_level=override_risk or metadata.get("risk_level", "low"),
                )
            if clean_mode in {ExecutionMode.AGENT_TEAM.value, "team", "agent_team"}:
                return self._create_plan(
                    task,
                    mode=ExecutionMode.AGENT_TEAM,
                    rationale="Explicit user override selected agent_team mode",
                    risk_level=override_risk or metadata.get("risk_level", "high"),
                )

        # 2. Automated evaluation via profiler
        profile = self._profiler.profile(task)

        # Complex task indicators: high reasoning, high complexity, security/architecture keywords
        is_complex = (
            profile.complexity >= 3
            or profile.reasoning_requirement >= 4
            or profile.risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}
            or any(kw in title or kw in body for kw in ("architect", "refactor", "framework", "concurrency", "security"))
        )

        if is_complex:
            return self._create_plan(
                task,
                mode=ExecutionMode.AGENT_TEAM,
                rationale=(
                    f"Task complexity ({profile.complexity}) or risk ({profile.risk_level.value}) "
                    "requires multi-agent team decomposition (Architect, Developer, Reviewer)."
                ),
                risk_level=override_risk or profile.risk_level.value,
            )

        # Low complexity / routine fix -> Single Agent First
        return self._create_plan(
            task,
            mode=ExecutionMode.SINGLE_AGENT,
            rationale=(
                f"Task complexity ({profile.complexity}) and risk ({profile.risk_level.value}) "
                "are well-bounded; single implementation agent provides lower latency and lower token overhead."
            ),
            risk_level=override_risk or profile.risk_level.value,
        )

    def _create_plan(
        self,
        task: DeliveryTask,
        *,
        mode: ExecutionMode,
        rationale: str,
        risk_level: str,
    ) -> ExecutionPlan:
        allowed = tuple(x.strip() for x in task.metadata.get("allowed_paths", "").split(",") if x.strip())
        forbidden = tuple(x.strip() for x in task.metadata.get("forbidden_paths", "").split(",") if x.strip())
        test_cmd = task.metadata.get("test_command", "")
        budget = int(task.metadata.get("budget_limit", "3"))

        return ExecutionPlan(
            mode=mode,
            rationale=rationale,
            risk_level=risk_level,
            context_summary=f"Task {task.work_item.item_id}: {task.work_item.title}",
            allowed_paths=allowed,
            forbidden_paths=forbidden,
            test_command=test_cmd,
            budget_limit=budget,
            require_review=True,  # STRICT REQUIREMENT: BOTH branches require independent review
            metadata=dict(task.metadata),
        )
