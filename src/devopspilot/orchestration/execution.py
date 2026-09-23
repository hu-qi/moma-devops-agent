"""Composable execution decorators for delivery orchestration."""

from __future__ import annotations

from devopspilot.contracts.delivery import DeliveryTask, ExecutionResult, TaskExecutor
from devopspilot.contracts.execution import ChangePublisher


class PublishingTaskExecutor:
    """Turn a local-commit executor into a DeliveryLoop-ready executor.

    The inner executor may only create a validated local commit. The publisher
    owns remote side effects. DeliveryLoop sees published=True only after the
    publisher completes successfully.
    """

    def __init__(
        self,
        executor: TaskExecutor,
        publisher: ChangePublisher,
    ) -> None:
        self._executor = executor
        self._publisher = publisher

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        result = await self._executor.execute(task)
        if result.published:
            return result

        published = await self._publisher.publish(task, result)
        if not published.published:
            raise RuntimeError(
                "ChangePublisher completed without marking the execution as published"
            )
        if published.commit_sha != result.commit_sha:
            raise RuntimeError(
                "Publisher changed commit identity; publishing must preserve the "
                "validated local commit"
            )
        return published
