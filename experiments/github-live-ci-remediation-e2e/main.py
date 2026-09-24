"""Live GitHub CI failure -> AgentTeam remediation -> same PR -> green CI E2E."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

from devopspilot.adapters.git import (
    GitChangePublisher,
    GitExistingBranchWorkspaceProvider,
)
from devopspilot.adapters.github import (
    GitHubCIProvider,
    GitHubHTTPClient,
    GitHubSCMProvider,
)
from devopspilot.adapters.openjiuwen import (
    OpenJiuwenRemediationExecutor,
    OpenJiuwenTaskExecutor,
)
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import (
    CommentSubjectKind,
    CommentSubjectRef,
)
from devopspilot.orchestration import (
    AutonomousDeliveryControlPlane,
    BoundedRemediationPolicy,
    PublishingTaskExecutor,
    RuleBasedCIFailureAnalyzer,
)
from devopspilot.persistence import SQLiteRemediationLedger


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "e2e" / "fixtures" / "ci_remediation" / "app.py"
CANDIDATE_SOURCE = '''def status() -> str:\n    """Return the current remediation fixture status."""\n    return "candidate"\n'''


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def git(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    proc = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({proc.returncode}): {out}\n{err}"
        )
    return out.strip()


async def publish_failing_candidate(
    *,
    source_branch: str,
    base_commit: str,
) -> str:
    path = Path(tempfile.mkdtemp(prefix="devopspilot_candidate_"))
    path.rmdir()
    try:
        await git(
            "worktree",
            "add",
            "-b",
            source_branch,
            str(path),
            base_commit,
        )
        fixture = path / "e2e" / "fixtures" / "ci_remediation" / "app.py"
        fixture.write_text(CANDIDATE_SOURCE, encoding="utf-8")
        await git(
            "add",
            "e2e/fixtures/ci_remediation/app.py",
            cwd=path,
        )
        await git(
            "-c",
            "user.name=DevOpsPilot",
            "-c",
            "user.email=devopspilot@local",
            "commit",
            "-m",
            "test: publish failing remediation candidate",
            cwd=path,
        )
        sha = await git("rev-parse", "HEAD", cwd=path)
        await git(
            "push",
            "origin",
            f"{sha}:refs/heads/{source_branch}",
            cwd=path,
        )
        return sha
    finally:
        if path.exists():
            await git(
                "worktree",
                "remove",
                "--force",
                str(path),
                check=False,
            )
        await git("branch", "-D", source_branch, check=False)
        await git("worktree", "prune", check=False)


async def repository_ref(
    client: GitHubHTTPClient,
    repository_name: str,
):
    from devopspilot.contracts.providers import RepositoryRef

    data = await client.request_json(
        "GET",
        f"/repos/{repository_name}",
    )
    return RepositoryRef(
        provider_id="github",
        repository_id=str(data["id"]),
        full_name=data["full_name"],
        default_branch=data.get("default_branch"),
        web_url=data.get("html_url"),
    )


async def wait_fixture_run(
    client: GitHubHTTPClient,
    ci: GitHubCIProvider,
    repository_name: str,
    commit_sha: str,
    *,
    timeout_seconds: int = 300,
):
    attempts = max(1, timeout_seconds // 5)
    for attempt in range(1, attempts + 1):
        data = await client.request_json(
            "GET",
            (
                f"/repos/{repository_name}/actions/workflows/"
                "ci-remediation-fixture-ci.yml/runs"
            ),
            query={
                "head_sha": commit_sha,
                "event": "pull_request",
                "per_page": 10,
            },
        )
        runs = data.get("workflow_runs", [])
        if runs:
            item = runs[0]
            if item.get("status") == "completed":
                repository = await repository_ref(
                    client,
                    repository_name,
                )
                return await ci.get_run(
                    repository,
                    str(item["id"]),
                )
        if attempt % 6 == 0:
            print(
                "DEVOPSPILOT_REMEDIATION_CI_WAIT "
                f"sha={commit_sha} attempt={attempt}"
            )
        await asyncio.sleep(5)
    raise RuntimeError(
        f"Timed out waiting for fixture CI for {commit_sha}"
    )


async def main() -> None:
    repository_name = required("GITHUB_REPOSITORY")
    issue_number = required("DEVOPSPILOT_E2E_ISSUE")
    target_branch = required("DEVOPSPILOT_TARGET_BRANCH")
    github_token = required("GITHUB_TOKEN")
    run_id = required("GITHUB_RUN_ID")

    client = GitHubHTTPClient(token=github_token)
    scm = GitHubSCMProvider(client)
    ci = GitHubCIProvider(client)
    repository = await scm.get_repository(repository_name)
    work_item = await scm.get_work_item(
        repository,
        issue_number,
    )

    base_commit = await git("rev-parse", "HEAD")
    current_branch = os.getenv("GITHUB_REF_NAME", "").strip()
    if current_branch and current_branch != target_branch:
        raise RuntimeError(
            f"workflow checkout branch {current_branch!r} "
            f"!= target {target_branch!r}"
        )
    if 'return "broken"' not in FIXTURE.read_text(
        encoding="utf-8"
    ):
        raise RuntimeError(
            "CI remediation fixture base is not in broken state"
        )

    source_branch = (
        f"devopspilot/remediation-e2e-{issue_number}-{run_id}"
    )
    candidate_sha = await publish_failing_candidate(
        source_branch=source_branch,
        base_commit=base_commit,
    )

    task = DeliveryTask(
        repository=repository,
        work_item=work_item,
        target_branch=target_branch,
        metadata={
            "source_branch": source_branch,
            "allowed_paths": (
                "e2e/fixtures/ci_remediation/app.py"
            ),
            "forbidden_paths": (
                "e2e/fixtures/ci_remediation/test_app.py,"
                "e2e/fixtures/ci_remediation/reset.py"
            ),
            "max_changed_files": "1",
            "test_command": (
                "cd e2e/fixtures/ci_remediation "
                "&& python test_app.py"
            ),
        },
    )
    execution = ExecutionResult(
        source_branch=source_branch,
        commit_sha=candidate_sha,
        summary=(
            "Published controlled failing "
            "CI-remediation candidate."
        ),
        published=True,
    )
    change = await scm.create_change_request(
        repository,
        title=f"[Remediation E2E] {work_item.title}",
        body=(
            "## Controlled CI-remediation candidate\n\n"
            f"Source issue: #{issue_number}\n"
            f"Candidate commit: `{candidate_sha}`\n\n"
            "This PR is intentionally expected to fail its "
            "first fixture CI run. DevOpsPilot must repair "
            "the same source branch and make the next run pass."
        ),
        source_branch=source_branch,
        target_branch=target_branch,
    )
    await scm.add_comment(
        CommentSubjectRef(
            repository,
            issue_number,
            CommentSubjectKind.WORK_ITEM,
        ),
        body=(
            "DevOpsPilot remediation E2E opened "
            f"PR #{change.change_id} with intentional "
            f"failing candidate `{candidate_sha}`."
        ),
    )

    failed_run = await wait_fixture_run(
        client,
        ci,
        repository_name,
        candidate_sha,
    )
    if failed_run.conclusion != "failure":
        raise RuntimeError(
            "Expected first fixture CI to fail, got "
            f"{failed_run.conclusion!r}"
        )
    logs = tuple(
        [log async for log in ci.stream_logs(failed_run)]
    )
    if not logs:
        raise RuntimeError(
            "Failed fixture CI produced no logs"
        )
    print(
        "DEVOPSPILOT_REMEDIATION_FAILURE_CAPTURED "
        f"run={failed_run.run_id} logs={len(logs)}"
    )

    failed_state = DeliveryState(
        task=task,
        phase=DeliveryPhase.CI_FAILED,
        execution=execution,
        change_request=change,
        ci_run=failed_run,
        ci_logs=logs,
    )

    workspace_provider = GitExistingBranchWorkspaceProvider(
        ROOT
    )
    agent_executor = OpenJiuwenTaskExecutor(
        workspace_provider,
        max_iterations=24,
        completion_timeout=180.0,
    )
    publishing_executor = PublishingTaskExecutor(
        agent_executor,
        GitChangePublisher(),
    )
    remediator = OpenJiuwenRemediationExecutor(
        publishing_executor
    )
    with tempfile.TemporaryDirectory() as tmp:
        plane = AutonomousDeliveryControlPlane(
            ci=ci,
            analyzer=RuleBasedCIFailureAnalyzer(),
            remediator=remediator,
            ledger=SQLiteRemediationLedger(
                Path(tmp) / "remediation.sqlite3"
            ),
            policy=BoundedRemediationPolicy(
                max_patch_attempts=2,
                max_ci_retries=1,
            ),
        )
        remediated = await plane.handle_ci_failure(
            (
                "github-remediation-e2e-"
                f"{issue_number}-{run_id}"
            ),
            failed_state,
        )

    if (
        remediated.phase is not DeliveryPhase.CI_PENDING
        or remediated.execution is None
    ):
        raise RuntimeError(
            "Expected remediation to publish a new pending "
            f"commit, got {remediated.phase}"
        )
    repair_sha = remediated.execution.commit_sha
    if repair_sha == candidate_sha:
        raise RuntimeError(
            "Remediation did not produce a new commit"
        )
    print(
        "DEVOPSPILOT_REMEDIATION_COMMIT_PUBLISHED "
        f"sha={repair_sha}"
    )

    passed_run = await wait_fixture_run(
        client,
        ci,
        repository_name,
        repair_sha,
    )
    if passed_run.conclusion != "success":
        failure_logs = tuple(
            [log async for log in ci.stream_logs(passed_run)]
        )
        details = "\n\n".join(
            log.content[-3000:]
            for log in failure_logs
        )
        raise RuntimeError(
            "Expected remediated fixture CI success, got "
            f"{passed_run.conclusion!r}\n{details}"
        )

    report = "\n".join([
        "## DevOpsPilot Live CI Remediation Report",
        "",
        f"- Source issue: #{issue_number}",
        f"- Pull Request: #{change.change_id}",
        f"- Source branch: `{source_branch}`",
        f"- Initial failing commit: `{candidate_sha}`",
        f"- Initial failed CI run: `{failed_run.run_id}`",
        f"- AgentTeam repair commit: `{repair_sha}`",
        f"- Successful CI run: `{passed_run.run_id}`",
        (
            "- Runtime degraded: `"
            f"{remediated.execution.metadata.get('runtime_degraded', 'false')}"
            "`"
        ),
        (
            "- Leader model: `"
            f"{remediated.execution.metadata.get('leader_model', '')}"
            "`"
        ),
        (
            "- Coding model: `"
            f"{remediated.execution.metadata.get('coding_model', '')}"
            "`"
        ),
        (
            "- Review model: `"
            f"{remediated.execution.metadata.get('review_model', '')}"
            "`"
        ),
        "",
        (
            "**Result: VERIFIED — CI failure was repaired "
            "on the same PR source branch.**"
        ),
    ])
    await scm.add_comment(
        CommentSubjectRef(
            repository,
            change.change_id,
            CommentSubjectKind.CHANGE_REQUEST,
        ),
        body=report,
    )
    await client.request_json(
        "PATCH",
        f"/repos/{repository_name}/pulls/{change.change_id}",
        body={"state": "closed"},
    )
    await client.request_json(
        "PATCH",
        f"/repos/{repository_name}/issues/{issue_number}",
        body={
            "state": "closed",
            "state_reason": "completed",
        },
    )
    await git(
        "push",
        "origin",
        "--delete",
        source_branch,
        check=False,
    )

    print(
        "GITHUB_LIVE_REMEDIATION_INITIAL_CI_FAILED_OK"
    )
    print("GITHUB_LIVE_REMEDIATION_AGENTTEAM_OK")
    print(
        "GITHUB_LIVE_REMEDIATION_SAME_BRANCH_PUSH_OK"
    )
    print(
        "GITHUB_LIVE_REMEDIATION_CI_RECOVERED_OK"
    )
    print("GITHUB_LIVE_REMEDIATION_VERIFIED_OK")


if __name__ == "__main__":
    asyncio.run(main())
