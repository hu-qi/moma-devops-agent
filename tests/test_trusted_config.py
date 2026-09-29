"""C08: trusted delivery config must flow from operator env through
task.metadata to workspace metadata, where executor/CI/verifier enforce it."""

import asyncio

from devopspilot.cli.assembly import load_trusted_delivery_config
from devopspilot.contracts.delivery import DeliveryTask
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef


class _FakeSCM:
    async def get_repository(self, repository_id):
        return RepositoryRef(provider_id="mock", repository_id="r1", full_name=repository_id, default_branch="main")

    async def get_work_item(self, repository, item_id):
        return WorkItemRef(repository=repository, item_id=item_id, title="t")


def test_load_trusted_delivery_config_reads_operator_env() -> None:
    env = {
        "DEVOPSPILOT_TEST_COMMAND": "python -m pytest -q",
        "DEVOPSPILOT_ALLOWED_PATHS": "src/,tests/app.py",
        "DEVOPSPILOT_FORBIDDEN_PATHS": "tests/test_oracle.py",
        "DEVOPSPILOT_REQUIRED_CHECKS": "unit,lint",
        "DEVOPSPILOT_REQUIRE_REVIEW": "true",
    }
    config = load_trusted_delivery_config(env)
    assert config == {
        "test_command": "python -m pytest -q",
        "allowed_paths": "src/,tests/app.py",
        "forbidden_paths": "tests/test_oracle.py",
        "required_checks": "unit,lint",
        "require_review": "true",
    }

    # Empty env -> no keys injected (defaults stay untouched)
    assert load_trusted_delivery_config({}) == {}
    # Invalid require_review value is dropped, not guessed
    assert "require_review" not in load_trusted_delivery_config({"DEVOPSPILOT_REQUIRE_REVIEW": "maybe"})


def test_trusted_config_flows_into_task_metadata() -> None:
    from devopspilot.orchestration.delivery_loop import DeliveryLoop

    loop = DeliveryLoop(scm=_FakeSCM(), ci=None, executor=None, verifier=None)  # type: ignore[arg-type]
    trusted = load_trusted_delivery_config({
        "DEVOPSPILOT_TEST_COMMAND": "python -m pytest -q",
        "DEVOPSPILOT_FORBIDDEN_PATHS": "tests/test_oracle.py",
        "DEVOPSPILOT_REQUIRED_CHECKS": "unit",
        "DEVOPSPILOT_REQUIRE_REVIEW": "true",
    })
    state = asyncio.run(loop.prepare_task(
        repository_id="org/repo",
        work_item_id="1",
        task_metadata={"delivery_id": "d1", **trusted},
    ))
    task: DeliveryTask = state.task
    # Executor reads these from workspace.metadata (inherited from task.metadata)
    assert task.metadata.get("test_command") == "python -m pytest -q"
    assert task.metadata.get("forbidden_paths") == "tests/test_oracle.py"
    assert task.metadata.get("require_review") == "true"
    # CI aggregator reads required_checks from task.metadata
    assert task.metadata.get("required_checks") == "unit"
