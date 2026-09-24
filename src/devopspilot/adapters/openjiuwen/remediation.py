"""OpenJiuwen remediation adapter for an existing delivery branch."""

from __future__ import annotations

from dataclasses import replace

from devopspilot.contracts.delivery import (
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
    TaskExecutor,
)
from devopspilot.contracts.remediation import (
    CIFailureAnalysis,
    RemediationExecutor,
)


class OpenJiuwenRemediationExecutor(RemediationExecutor):
    """Adapt the standard TaskExecutor to a CI-failure remediation turn."""

    def __init__(self, executor: TaskExecutor) -> None:
        self._executor = executor

    async def remediate(
        self,
        state: DeliveryState,
        analysis: CIFailureAnalysis,
        *,
        attempt: int,
    ) -> ExecutionResult:
        if state.execution is None:
            raise ValueError("remediation requires an existing execution")

        evidence = "\n\n".join(
            analysis.evidence
        ) or "(no CI log evidence captured)"
        work_item = replace(
            state.task.work_item,
            body=(
                f"{state.task.work_item.body}\n\n"
                "---\n\n"
                f"CI remediation attempt {attempt}.\n"
                f"Failure classification: {analysis.kind.value}.\n"
                f"Failure summary: {analysis.summary}\n\n"
                "CI evidence:\n"
                f"{evidence}\n\n"
                "Repair the existing PR/MR source branch with the smallest correct "
                "change. Re-run the repository-provided verification."
            ),
        )
        metadata = {
            **dict(state.task.metadata),
            "source_branch": state.execution.source_branch,
            "execution_id": f"remediation-{attempt}",
            "remediation_attempt": str(attempt),
            "remediation_failure_kind": analysis.kind.value,
        }
        task = DeliveryTask(
            repository=state.task.repository,
            work_item=work_item,
            target_branch=state.task.target_branch,
            metadata=metadata,
        )
        result = await self._executor.execute(task)
        if result.source_branch != state.execution.source_branch:
            raise RuntimeError(
                "remediation executor changed source branch identity"
            )
        return result
