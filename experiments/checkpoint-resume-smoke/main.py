"""Smoke test for staged checkpoints and fault-injected resume without duplicated side-effects."""

from __future__ import annotations

import asyncio
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    DeliveryVerifier,
    ExecutionResult,
    VerificationResult,
)
from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CIRunRef,
    CommentSubjectKind,
    CommentSubjectRef,
    RepositoryRef,
    WorkItemRef,
)
from devopspilot.orchestration.delivery_loop import DeliveryLoop
from devopspilot.orchestration.service import DeliveryOrchestrator
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore

REPO = RepositoryRef(provider_id="mock", repository_id="repo-1", full_name="org/repo", default_branch="main")
WORK_ITEM = WorkItemRef(repository=REPO, item_id="item-resume", title="resume test")


class InstrumentedSCM:
    def __init__(self) -> None:
        self.create_pr_calls = 0
        self.comment_calls = 0

    async def get_repository(self, repo_id: str) -> RepositoryRef:
        return REPO

    async def get_work_item(self, repo: RepositoryRef, item_id: str) -> WorkItemRef:
        return WORK_ITEM

    async def create_change_request(
        self,
        repo: RepositoryRef,
        *,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
    ) -> ChangeRequestRef:
        self.create_pr_calls += 1
        return ChangeRequestRef(
            repository=repo,
            change_id=f"pr-{self.create_pr_calls}",
            title=title,
            source_branch=source_branch,
            target_branch=target_branch,
            state="open",
        )

    async def add_comment(self, subject: CommentSubjectRef, *, body: str) -> None:
        self.comment_calls += 1


class InstrumentedExecutor:
    def __init__(self) -> None:
        self.execute_calls = 0

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        self.execute_calls += 1
        return ExecutionResult(
            source_branch="feat-branch",
            commit_sha=f"commit-{self.execute_calls}",
            summary="executed",
            published=True,
        )


class MockCI:
    def __init__(self) -> None:
        self.list_runs_calls = 0

    async def list_runs(self, repo: RepositoryRef, *, commit_sha: str | None = None, ref: str | None = None, limit: int = 100) -> tuple[CIRunRef, ...]:
        self.list_runs_calls += 1
        return (
            CIRunRef(
                provider_id="mock",
                run_id=f"run-{self.list_runs_calls}",
                repository=repo,
                status="completed",
                conclusion="success",
                commit_sha=commit_sha,
                attempt=1,
            ),
        )


class MockVerifier(DeliveryVerifier):
    async def verify(self, state: DeliveryState) -> VerificationResult:
        return VerificationResult(accepted=True, summary="ok")


async def test_checkpoint_and_resume_after_execution_crash() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_resume_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)
        scm = InstrumentedSCM()
        executor = InstrumentedExecutor()
        ci = MockCI()
        verifier = MockVerifier()

        loop = DeliveryLoop(scm=scm, ci=ci, executor=executor, verifier=verifier)  # type: ignore[arg-type]
        orchestrator = DeliveryOrchestrator(loop=loop, store=store)

        # 1. Fault injection: simulate execution crashed AFTER saving EXECUTED checkpoint (before PR created)
        prepared = await loop.prepare_task(
            repository_id="repo-1",
            work_item_id="item-resume",
            target_branch="main",
        )
        saved_rec = await store.save("deliv-crash-test", prepared, expected_version=0)
        executed = await loop.step_execute(saved_rec.state)
        # Checkpoint 2 saved (commit-1 produced)
        saved_exec = await store.save("deliv-crash-test", executed, expected_version=saved_rec.version)

        # At this point, commit is produced, but NO PR has been opened yet
        assert executor.execute_calls == 1
        assert scm.create_pr_calls == 0
        assert saved_exec.state.phase is DeliveryPhase.EXECUTED

        # 2. Crash simulated: new orchestrator instance restarts and resumes "deliv-crash-test"
        resumed = await orchestrator.resume("deliv-crash-test")

        # Must reach CHANGE_OPENED
        assert resumed.state.phase is DeliveryPhase.CHANGE_OPENED
        # CRITICAL ASSERTION: executor MUST NOT be called again (avoid duplicated agent runs / duplicate commits)
        assert executor.execute_calls == 1, "Executor was duplicated upon resume!"
        assert resumed.state.execution is not None
        assert resumed.state.execution.commit_sha == "commit-1"
        # PR is opened now
        assert scm.create_pr_calls == 1
        assert scm.comment_calls == 1
        print("CHECKPOINT_RESUME_NO_DUPLICATE_EXECUTION_OK")

        # 3. Resume from CHANGE_OPENED -> automatically reconciles CI
        resumed_ci = await orchestrator.resume("deliv-crash-test")
        assert resumed_ci.state.phase is DeliveryPhase.CI_PASSED
        assert ci.list_runs_calls == 1
        print("CHECKPOINT_RESUME_ADVANCES_TO_CI_PASSED_OK")

        # 4. Resume from CI_PASSED -> automatically verifies
        resumed_verified = await orchestrator.resume("deliv-crash-test")
        assert resumed_verified.state.phase is DeliveryPhase.VERIFIED
        assert resumed_verified.state.verification is not None
        assert resumed_verified.state.verification.accepted is True
        print("CHECKPOINT_RESUME_ADVANCES_TO_VERIFIED_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def main() -> None:
    await test_checkpoint_and_resume_after_execution_crash()
    print("ALL CHECKPOINT RESUME SMOKE TESTS PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
