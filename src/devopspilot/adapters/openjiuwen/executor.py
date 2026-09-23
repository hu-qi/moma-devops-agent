"""OpenJiuwen-backed implementation of the DevOpsPilot TaskExecutor port."""

from __future__ import annotations

import asyncio
import os
import shlex
from dataclasses import replace
from pathlib import Path

from devopspilot.contracts.delivery import DeliveryTask, ExecutionResult
from devopspilot.contracts.execution import ExecutionWorkspace, WorkspaceProvider


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


async def _run(
    *args: str,
    cwd: Path,
    check: bool = True,
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    out = stdout.decode("utf-8", errors="replace")
    err = stderr.decode("utf-8", errors="replace")
    if check and process.returncode != 0:
        command = " ".join(shlex.quote(x) for x in args)
        raise RuntimeError(
            f"Command failed ({process.returncode}): {command}\n{out}\n{err}"
        )
    return process.returncode or 0, out, err


class OpenJiuwenTaskExecutor:
    """Execute a delivery task with a dynamic Coding + Review AgentTeam.

    The executor makes a local commit but deliberately does not publish it.
    A provider-specific ChangePublisher is responsible for setting
    ExecutionResult.published=True after an actual push.
    """

    def __init__(
        self,
        workspace_provider: WorkspaceProvider,
        *,
        max_iterations: int = 32,
        completion_timeout: float = 600.0,
    ) -> None:
        self._workspace_provider = workspace_provider
        self._max_iterations = max_iterations
        self._completion_timeout = completion_timeout

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        workspace = await self._workspace_provider.prepare(task)
        try:
            return await self._execute_in_workspace(task, workspace)
        except Exception:
            await self._workspace_provider.cleanup(workspace)
            raise

    async def _execute_in_workspace(
        self,
        task: DeliveryTask,
        workspace: ExecutionWorkspace,
    ) -> ExecutionResult:
        from openjiuwen.agent_teams import TeamAgentSpec
        from openjiuwen.core.runner import Runner

        default_model = _required_env("MOMA_MODEL")
        reasoning_model = os.getenv("MOMA_REASONING_MODEL", default_model).strip() or default_model
        coding_model = os.getenv("MOMA_CODING_MODEL", default_model).strip() or default_model
        review_model = os.getenv("MOMA_REVIEW_MODEL", default_model).strip() or default_model

        def model_spec(model_name: str) -> dict:
            return {
                "model": {
                    "model_client_config": {
                        "client_provider": "OpenAI",
                        "api_key": _required_env("MOMA_API_KEY"),
                        "api_base": _required_env("MOMA_API_BASE"),
                        "endpoint_profile": "openai_compatible",
                        "timeout": 120,
                    },
                    "model_request_config": {
                        "model": model_name,
                        "temperature": 0,
                    },
                },
                "max_iterations": self._max_iterations,
                "completion_timeout": self._completion_timeout,
            }

        spec = TeamAgentSpec.model_validate({
            "agents": {
                "leader": model_spec(reasoning_model),
                "teammate": model_spec(coding_model),
            },
            "transport": {"type": "inprocess"},
            "storage": {"type": "inmemory"},
            "team_name": f"devopspilot-exec-{task.work_item.item_id}",
            "lifecycle": "temporary",
            "teammate_mode": "build_mode",
            "spawn_mode": "inprocess",
            "leader": {
                "member_name": "devops_leader",
                "display_name": "DevOps Leader",
                "persona": (
                    "You are DevOpsPilot's software-delivery leader. "
                    "Work only in the repository workspace given by the task. "
                    "Dynamically create exactly two specialists named coding_agent "
                    "and review_agent. coding_agent must inspect and implement the "
                    "smallest correct patch. review_agent must independently inspect "
                    "the diff, constraints and test evidence. The leader may finalize "
                    "the patch only after review. Never modify forbidden files. "
                    "Never push or create remote PRs. Do not commit; DevOpsPilot will "
                    "validate and commit after the team finishes."
                ),
            },
        })

        # Per-member model aliases are currently selected through the runtime's
        # teammate model slot. Preserve requested reviewer profile in metadata
        # until TeamAgentSpec exposes per-dynamic-member model binding.
        query = self._build_query(task, workspace, review_model)

        await Runner.start()
        try:
            async for _chunk in Runner.run_agent_team_streaming(
                agent_team=spec,
                inputs={"query": query},
                session=f"delivery-{task.repository.repository_id}-{task.work_item.item_id}",
            ):
                pass
        finally:
            await Runner.stop()

        test_command = workspace.metadata.get("test_command", "").strip()
        test_summary = ""
        if test_command:
            code, out, err = await asyncio.create_subprocess_shell(
                test_command,
                cwd=str(workspace.path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            ).communicate()  # type: ignore[assignment]

        # Use exec form for product validation below; shell is only needed for
        # benchmark/user-provided composite commands and never receives secrets.
        if test_command:
            proc = await asyncio.create_subprocess_shell(
                test_command,
                cwd=str(workspace.path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_b, stderr_b = await proc.communicate()
            test_summary = (
                stdout_b.decode("utf-8", errors="replace")
                + stderr_b.decode("utf-8", errors="replace")
            )[-4000:]
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Independent verification failed ({proc.returncode}):\n{test_summary}"
                )

        await self._validate_paths(workspace)
        diff = (await _run("git", "diff", "--", ".", cwd=workspace.path))[1]
        if not diff.strip():
            raise RuntimeError("AgentTeam completed without producing a code change")

        await _run("git", "add", "-A", cwd=workspace.path)
        await _run(
            "git",
            "-c",
            "user.name=DevOpsPilot",
            "-c",
            "user.email=devopspilot@local",
            "commit",
            "-m",
            f"fix: resolve work item {task.work_item.item_id}",
            cwd=workspace.path,
        )
        commit_sha = (await _run(
            "git", "rev-parse", "HEAD", cwd=workspace.path
        ))[1].strip()

        return ExecutionResult(
            source_branch=workspace.source_branch,
            commit_sha=commit_sha,
            summary=(
                f"OpenJiuwen AgentTeam completed work item {task.work_item.item_id}; "
                "independent verification passed and a local commit was created."
            ),
            published=False,
            test_summary=test_summary.strip(),
            metadata={
                "workspace_path": str(workspace.path),
                "base_commit": workspace.base_commit,
                "review_model_requested": review_model,
            },
        )

    async def _validate_paths(self, workspace: ExecutionWorkspace) -> None:
        allowed = {
            x for x in workspace.metadata.get("allowed_paths", "").split(",") if x
        }
        forbidden = {
            x for x in workspace.metadata.get("forbidden_paths", "").split(",") if x
        }
        changed = (await _run(
            "git", "status", "--porcelain", cwd=workspace.path
        ))[1]
        paths = {
            line[3:].strip()
            for line in changed.splitlines()
            if len(line) >= 4
        }
        if forbidden & paths:
            raise RuntimeError(
                f"AgentTeam modified forbidden paths: {sorted(forbidden & paths)}"
            )
        if allowed and not paths.issubset(allowed):
            raise RuntimeError(
                f"AgentTeam modified paths outside allow-list: {sorted(paths - allowed)}"
            )

    @staticmethod
    def _build_query(
        task: DeliveryTask,
        workspace: ExecutionWorkspace,
        review_model: str,
    ) -> str:
        allowed = workspace.metadata.get("allowed_paths", "(not specified)")
        forbidden = workspace.metadata.get("forbidden_paths", "(none)")
        test_command = workspace.metadata.get("test_command", "(not specified)")
        return f"""
Repository workspace: {workspace.path}
Source branch: {workspace.source_branch}

Work item #{task.work_item.item_id}: {task.work_item.title}

Description:
{task.work_item.body}

Constraints:
- Allowed paths: {allowed}
- Forbidden paths: {forbidden}
- Independent test command: {test_command}
- Do not commit, push, or modify anything outside {workspace.path}
- Create coding_agent and review_agent dynamically.
- coding_agent must implement the minimal patch and run tests.
- review_agent must independently inspect the resulting diff and test evidence.
- Requested review model profile: {review_model}
- The leader must leave the verified working-tree changes in place for
  DevOpsPilot to validate and commit.
""".strip()
