"""Provider-neutral Issue -> PR/MR -> CI delivery orchestration."""

from __future__ import annotations

from dataclasses import replace

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    DeliveryVerifier,
    TaskExecutor,
)
from devopspilot.contracts.providers import (
    CICapability,
    CIProvider,
    CommentSubjectKind,
    CommentSubjectRef,
    SCMProvider,
)


class DeliveryLoop:
    """Resumable state machine for the first DevOpsPilot product loop.

    The loop deliberately does not wait or poll in the background. Event or
    webhook handlers call reconcile_ci() as CI state changes.
    """

    def __init__(
        self,
        *,
        scm: SCMProvider,
        ci: CIProvider,
        executor: TaskExecutor,
        verifier: DeliveryVerifier,
    ) -> None:
        self._scm = scm
        self._ci = ci
        self._executor = executor
        self._verifier = verifier

    async def start(
        self,
        *,
        repository_id: str,
        work_item_id: str,
        target_branch: str | None = None,
    ) -> DeliveryState:
        repository = await self._scm.get_repository(repository_id)
        work_item = await self._scm.get_work_item(repository, work_item_id)
        resolved_target = target_branch or repository.default_branch
        if not resolved_target:
            raise ValueError("Target branch is required when repository has no default branch")

        task = DeliveryTask(
            repository=repository,
            work_item=work_item,
            target_branch=resolved_target,
        )
        state = DeliveryState(task=task, phase=DeliveryPhase.RECEIVED)

        execution = await self._executor.execute(task)
        if not execution.published:
            raise RuntimeError(
                "TaskExecutor returned an unpublished branch; "
                "DeliveryLoop cannot create a change request"
            )
        state = replace(state, phase=DeliveryPhase.EXECUTED, execution=execution)

        change = await self._scm.create_change_request(
            repository,
            title=work_item.title,
            body=self._change_body(state),
            source_branch=execution.source_branch,
            target_branch=resolved_target,
        )
        await self._scm.add_comment(
            CommentSubjectRef(
                repository=repository,
                subject_id=work_item.item_id,
                kind=CommentSubjectKind.WORK_ITEM,
            ),
            body=(
                f"DevOpsPilot opened change request {change.change_id} "
                f"from {execution.source_branch} for commit {execution.commit_sha}."
            ),
        )
        return replace(
            state,
            phase=DeliveryPhase.CHANGE_OPENED,
            change_request=change,
        )

    async def reconcile_ci(self, state: DeliveryState) -> DeliveryState:
        if state.execution is None or state.change_request is None:
            raise ValueError("CI reconciliation requires an executed task and change request")

        runs = await self._ci.list_runs(
            state.task.repository,
            commit_sha=state.execution.commit_sha,
            ref=state.execution.source_branch,
            limit=20,
        )
        if not runs:
            return replace(state, phase=DeliveryPhase.CI_PENDING)

        run = runs[0]
        normalized = replace(state, ci_run=run)

        if run.status != "completed" and run.conclusion is None:
            return replace(normalized, phase=DeliveryPhase.CI_PENDING)

        if run.conclusion == "success":
            return replace(normalized, phase=DeliveryPhase.CI_PASSED)

        logs: tuple = ()
        capabilities = await self._ci.capabilities()
        if CICapability.LOGS in capabilities:
            logs = tuple([log async for log in self._ci.stream_logs(run)])
        return replace(
            normalized,
            phase=DeliveryPhase.CI_FAILED,
            ci_logs=logs,
        )

    async def verify(self, state: DeliveryState) -> DeliveryState:
        if state.phase not in {DeliveryPhase.CI_PASSED, DeliveryPhase.CI_FAILED}:
            raise ValueError(f"Cannot verify delivery from phase {state.phase}")
        result = await self._verifier.verify(state)
        return replace(
            state,
            phase=DeliveryPhase.VERIFIED if result.accepted else DeliveryPhase.REJECTED,
            verification=result,
        )

    @staticmethod
    def _change_body(state: DeliveryState) -> str:
        assert state.execution is not None
        parts = [
            "## DevOpsPilot Delivery",
            "",
            state.execution.summary,
        ]
        if state.execution.test_summary:
            parts.extend(["", "### Tests", "", state.execution.test_summary])
        parts.extend([
            "",
            f"Source issue/work item: {state.task.work_item.item_id}",
            f"Commit: {state.execution.commit_sha}",
        ])
        return "\n".join(parts)
