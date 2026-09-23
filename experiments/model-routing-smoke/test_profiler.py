"""Smoke for DeliveryTask -> TaskProfile derivation."""

from __future__ import annotations

from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.model_intelligence import RiskLevel, TaskType
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.routing.profiler import DeliveryTaskProfiler


def main() -> None:
    repo = RepositoryRef(
        provider_id="github",
        repository_id="42",
        full_name="acme/demo",
        default_branch="main",
    )
    task = DeliveryTask(
        repository=repo,
        work_item=WorkItemRef(
            repository=repo,
            item_id="7",
            title="Fix auth regression",
            body="Repair the failing authentication path.",
            labels=("bug", "security", "python"),
        ),
        target_branch="main",
        metadata={
            "complexity": "4",
            "coding_requirement": "5",
            "privacy_level": "enterprise",
        },
    )

    profile = DeliveryTaskProfiler().profile(task)
    assert profile.task_type is TaskType.CODING
    assert profile.risk_level is RiskLevel.HIGH
    assert profile.complexity == 4
    assert profile.reasoning_requirement == 4
    assert profile.coding_requirement == 5
    assert profile.review_requirement == 5
    assert profile.project == "acme/demo"
    assert profile.tags == ("bug", "python", "security")
    assert profile.privacy_level == "enterprise"

    explicit = DeliveryTask(
        repository=repo,
        work_item=task.work_item,
        target_branch="main",
        metadata={"risk_level": "low", "complexity": "1"},
    )
    explicit_profile = DeliveryTaskProfiler().profile(explicit)
    assert explicit_profile.risk_level is RiskLevel.LOW
    assert explicit_profile.complexity == 1

    print("DELIVERY_TASK_PROFILE_OK")
    print("RISK_LABEL_HINTS_OK")
    print("EXPLICIT_PROFILE_OVERRIDE_OK")


if __name__ == "__main__":
    main()
