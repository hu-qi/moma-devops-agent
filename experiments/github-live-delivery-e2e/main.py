"""Live GitHub Issue -> AgentTeam -> PR -> Actions -> verify E2E."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from devopspilot.adapters.git import GitChangePublisher, GitWorktreeWorkspaceProvider
from devopspilot.adapters.github import GitHubCIProvider, GitHubHTTPClient, GitHubSCMProvider
from devopspilot.adapters.openjiuwen import OpenJiuwenTaskExecutor
from devopspilot.contracts.delivery import DeliveryPhase, DeliveryState, VerificationResult
from devopspilot.contracts.providers import CommentSubjectKind, CommentSubjectRef
from devopspilot.orchestration import DeliveryLoop, PublishingTaskExecutor


ROOT = Path(__file__).resolve().parents[2]


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


class SuccessVerifier:
    async def verify(self, state: DeliveryState) -> VerificationResult:
        accepted = (
            state.phase is DeliveryPhase.CI_PASSED
            and state.ci_run is not None
            and state.ci_run.conclusion == "success"
        )
        return VerificationResult(
            accepted=accepted,
            summary=(
                "GitHub Actions passed; live delivery accepted."
                if accepted
                else "GitHub Actions did not pass."
            ),
            evidence=(state.ci_run.run_id,) if state.ci_run else (),
        )


async def main() -> None:
    repository_name = required("GITHUB_REPOSITORY")
    issue_number = required("DEVOPSPILOT_E2E_ISSUE")
    github_token = required("GITHUB_TOKEN")
    run_id = required("GITHUB_RUN_ID")

    client = GitHubHTTPClient(token=github_token)
    scm = GitHubSCMProvider(client)
    ci = GitHubCIProvider(client)

    workspace_provider = GitWorktreeWorkspaceProvider(ROOT)
    agent_executor = OpenJiuwenTaskExecutor(
        workspace_provider,
        max_iterations=24,
        completion_timeout=180.0,
    )
    executor = PublishingTaskExecutor(
        agent_executor,
        GitChangePublisher(),
    )
    loop = DeliveryLoop(
        scm=scm,
        ci=ci,
        executor=executor,
        verifier=SuccessVerifier(),
    )

    source_branch = f"devopspilot/e2e-{issue_number}-{run_id}"
    state = await loop.start(
        repository_id=repository_name,
        work_item_id=issue_number,
        task_metadata={
            "source_branch": source_branch,
            "allowed_paths": "e2e/fixtures/github_delivery/app.py",
            "forbidden_paths": "e2e/fixtures/github_delivery/test_app.py",
            "max_changed_files": "1",
            "test_command": (
                "cd e2e/fixtures/github_delivery && python test_app.py"
            ),
        },
    )
    assert state.execution is not None
    assert state.change_request is not None
    assert state.execution.published is True

    print(
        "DEVOPSPILOT_E2E_CHANGE_OPENED "
        f"pr={state.change_request.change_id} "
        f"commit={state.execution.commit_sha} "
        f"branch={state.execution.source_branch}"
    )

    await ci.trigger(
        state.task.repository,
        ref=state.execution.source_branch,
        workflow_id="github-e2e-fixture-ci.yml",
        inputs={
            "source_branch": state.execution.source_branch,
            "expected_sha": state.execution.commit_sha,
        },
    )

    terminal: DeliveryState | None = None
    for attempt in range(1, 61):
        candidate = await loop.reconcile_ci(state)
        if candidate.phase in {DeliveryPhase.CI_PASSED, DeliveryPhase.CI_FAILED}:
            terminal = candidate
            break
        if attempt % 6 == 0:
            print(f"DEVOPSPILOT_E2E_CI_WAIT attempt={attempt}")
        await asyncio.sleep(5)

    if terminal is None:
        raise RuntimeError("Timed out waiting for GitHub fixture CI")

    verified = await loop.verify(terminal)
    if verified.phase is not DeliveryPhase.VERIFIED:
        details = "\n\n".join(
            f"### {log.job_name}\n{log.content[-4000:]}"
            for log in terminal.ci_logs
        )
        raise RuntimeError(
            "Live GitHub E2E verification failed"
            + (f"\n{details}" if details else "")
        )

    report = [
        "## DevOpsPilot Live Delivery Report",
        "",
        f"- Issue: #{issue_number}",
        f"- Pull Request: #{state.change_request.change_id}",
        f"- Source branch: {state.execution.source_branch}",
        f"- Commit: {state.execution.commit_sha}",
        f"- CI run: {verified.ci_run.run_id if verified.ci_run else ''}",
        f"- CI conclusion: {verified.ci_run.conclusion if verified.ci_run else ''}",
        f"- Runtime degraded: {state.execution.metadata.get('runtime_degraded', 'false')}",
        f"- Leader model: {state.execution.metadata.get('leader_model', '')}",
        f"- Coding model: {state.execution.metadata.get('coding_model', '')}",
        f"- Review model: {state.execution.metadata.get('review_model', '')}",
        f"- Trajectory: {state.execution.metadata.get('trajectory_id', '')}",
        "",
        "**Result: VERIFIED**",
    ]
    await scm.add_comment(
        CommentSubjectRef(
            repository=state.task.repository,
            subject_id=state.change_request.change_id,
            kind=CommentSubjectKind.CHANGE_REQUEST,
        ),
        body="\n".join(report),
    )

    print("GITHUB_LIVE_ISSUE_OK")
    print("GITHUB_LIVE_AGENTTEAM_OK")
    print("GITHUB_LIVE_PUBLISH_OK")
    print("GITHUB_LIVE_PR_OK")
    print("GITHUB_LIVE_CI_OK")
    print("GITHUB_LIVE_DELIVERY_VERIFIED_OK")


if __name__ == "__main__":
    asyncio.run(main())
