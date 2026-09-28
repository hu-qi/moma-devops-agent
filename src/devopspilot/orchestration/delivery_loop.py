"""Provider-neutral Issue -> PR/MR -> CI delivery orchestration."""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from devopspilot.contracts.branding import BrandConfig
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    DeliveryVerifier,
    TaskExecutor,
)
from devopspilot.contracts.industry import PackConfigurationError, PackRef
from devopspilot.contracts.providers import (
    CICapability,
    CIProvider,
    CommentSubjectKind,
    CommentSubjectRef,
    SCMProvider,
)
from devopspilot.orchestration.ci_aggregator import (
    CIAggregationStatus,
    aggregate_ci_runs,
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
        task_metadata: Mapping[str, str] | None = None,
    ) -> DeliveryState:
        state = await self.prepare_task(
            repository_id=repository_id,
            work_item_id=work_item_id,
            target_branch=target_branch,
            task_metadata=task_metadata,
        )
        state = await self.step_execute(state)
        return await self.step_open_change(state)

    async def prepare_task(
        self,
        *,
        repository_id: str,
        work_item_id: str,
        target_branch: str | None = None,
        task_metadata: Mapping[str, str] | None = None,
    ) -> DeliveryState:
        repository = await self._scm.get_repository(repository_id)
        work_item = await self._scm.get_work_item(repository, work_item_id)
        resolved_target = target_branch or repository.default_branch
        if not resolved_target:
            raise ValueError("Target branch is required when repository has no default branch")

        meta = dict(task_metadata or {})
        pack_ref = None
        raw_pack = meta.get("industry_pack") or meta.get("pack_ref")
        if raw_pack:
            import json
            try:
                if isinstance(raw_pack, str):
                    data = json.loads(raw_pack)
                elif isinstance(raw_pack, dict):
                    data = raw_pack
                elif hasattr(raw_pack, "to_dict"):
                    data = raw_pack.to_dict()
                else:
                    data = dict(raw_pack)
                pack_ref = PackRef.from_dict(data)
            except Exception as exc:
                raise PackConfigurationError(
                    f"Invalid industry_pack configuration: {exc}"
                ) from exc

        task = DeliveryTask(
            repository=repository,
            work_item=work_item,
            target_branch=resolved_target,
            metadata=meta,
            pack_ref=pack_ref,
        )
        return DeliveryState(task=task, phase=DeliveryPhase.RECEIVED)

    async def step_execute(self, state: DeliveryState) -> DeliveryState:
        if state.phase is not DeliveryPhase.RECEIVED:
            raise ValueError(f"step_execute requires phase == RECEIVED, got {state.phase}")
        execution = await self._executor.execute(state.task)
        if not execution.published:
            raise RuntimeError(
                "TaskExecutor returned an unpublished branch; "
                "DeliveryLoop cannot create a change request"
            )
        return replace(state, phase=DeliveryPhase.EXECUTED, execution=execution)

    async def step_open_change(self, state: DeliveryState) -> DeliveryState:
        if state.phase is not DeliveryPhase.EXECUTED or state.execution is None:
            raise ValueError(f"step_open_change requires phase == EXECUTED and execution, got {state.phase}")

        change = await self._scm.create_change_request(
            state.task.repository,
            title=state.task.work_item.title,
            body=self._change_body(state),
            source_branch=state.execution.source_branch,
            target_branch=state.task.target_branch,
        )
        brand = BrandConfig.from_env()
        await self._scm.add_comment(
            CommentSubjectRef(
                repository=state.task.repository,
                subject_id=state.task.work_item.item_id,
                kind=CommentSubjectKind.WORK_ITEM,
            ),
            body=(
                f"{brand.devopspilot_markdown} opened change request {change.change_id} "
                f"from {state.execution.source_branch} for commit {state.execution.commit_sha}."
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

        req_checks_raw = (
            state.task.metadata.get("required_checks")
            or state.task.metadata.get("required_workflows")
            or ""
        )
        required_checks = (
            tuple(x.strip() for x in req_checks_raw.split(",") if x.strip())
            if req_checks_raw
            else None
        )

        runs = await self._ci.list_runs(
            state.task.repository,
            commit_sha=state.execution.commit_sha,
            ref=state.execution.source_branch,
            limit=100,
        )

        aggregation = aggregate_ci_runs(
            runs,
            expected_commit_sha=state.execution.commit_sha,
            required_checks=required_checks,
        )

        primary_run = aggregation.primary_run or (runs[0] if runs else None)
        normalized = replace(state, ci_run=primary_run)

        if aggregation.status is CIAggregationStatus.PENDING:
            return replace(normalized, phase=DeliveryPhase.CI_PENDING)

        if aggregation.status is CIAggregationStatus.PASSED:
            return replace(normalized, phase=DeliveryPhase.CI_PASSED)

        # FAILED
        logs: tuple = ()
        capabilities = await self._ci.capabilities()
        if CICapability.LOGS in capabilities and primary_run is not None:
            logs = tuple([log async for log in self._ci.stream_logs(primary_run)])
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
        from devopspilot.utils.model_text import strip_think_tags

        brand = BrandConfig.from_env()
        clean_summary = strip_think_tags(state.execution.summary).strip()
        parts = [
            f"## {brand.devopspilot_markdown} Delivery",
            "",
            clean_summary,
        ]
        if state.execution.test_summary:
            clean_test_summary = strip_think_tags(state.execution.test_summary).strip()
            parts.extend(["", "### Tests", "", clean_test_summary])
        parts.extend([
            "",
            f"Source issue/work item: {state.task.work_item.item_id}",
            f"Commit: {state.execution.commit_sha}",
            brand.format_pr_footer(),
        ])
        return "\n".join(parts)
