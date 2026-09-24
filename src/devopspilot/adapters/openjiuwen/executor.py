"""OpenJiuwen-backed implementation of the DevOpsPilot TaskExecutor port."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from devopspilot.contracts.delivery import DeliveryTask, ExecutionResult
from devopspilot.contracts.execution import ExecutionWorkspace, WorkspaceProvider
from devopspilot.contracts.providers import MaaSProvider
from devopspilot.evaluation.metrics import trajectory_runtime_metrics
from devopspilot.routing import AgentTeamModelPlanner, DeliveryTaskProfiler
from devopspilot.trajectory import OpenJiuwenTrajectoryCapture

from .model_router import build_team_model_routing


def _runtime_slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip(".-")
    return normalized or "default"


class OpenJiuwenExecutionError(RuntimeError):
    """Execution failed after runtime evidence became available."""

    def __init__(
        self,
        message: str,
        *,
        metadata: dict[str, str] | None = None,
        test_summary: str = "",
    ) -> None:
        super().__init__(message)
        self.metadata = dict(metadata or {})
        self.test_summary = test_summary


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
        maas_provider: MaaSProvider | None = None,
        task_profiler: DeliveryTaskProfiler | None = None,
        max_iterations: int = 32,
        completion_timeout: float = 600.0,
    ) -> None:
        self._workspace_provider = workspace_provider
        self._maas_provider = maas_provider
        self._task_profiler = task_profiler or DeliveryTaskProfiler()
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

        from devopspilot.adapters.moma import MoMAProvider

        maas_provider = self._maas_provider or MoMAProvider.from_env()
        task_profile = self._task_profiler.profile(task)
        model_plan = await AgentTeamModelPlanner(maas_provider).plan(task_profile)
        model_routing = build_team_model_routing(
            model_plan,
            api_base=_required_env("MOMA_API_BASE"),
            api_key=_required_env("MOMA_API_KEY"),
            timeout=120.0,
        )

        configured_skills_dir = workspace.metadata.get("skills_dir", "").strip()
        enabled_skills = [
            item.strip()
            for item in workspace.metadata.get("enabled_skills", "").split(",")
            if item.strip()
        ]
        skill_mode = workspace.metadata.get("skill_mode", "all").strip() or "all"

        execution_id = _runtime_slug(
            workspace.metadata.get("execution_id", "default")
        )
        team_runtime_id = (
            f"{_runtime_slug(task.work_item.item_id)}-{execution_id}"
        )

        def model_spec(model_name: str) -> dict:
            # Fallback path if model-router allocation is unavailable.
            spec = {
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
                # DevOps coding agents do not consume image inputs. Explicitly
                # disable OpenJiuwen's automatic multimodal probe so text/code
                # models do not emit an expected HTTP 400 during startup.
                "enable_read_image_multimodal": False,
            }
            if configured_skills_dir:
                skill_params: dict[str, object] = {
                    "skill_mode": skill_mode,
                    "skills_dir": configured_skills_dir,
                }
                if enabled_skills:
                    skill_params["enabled_skills"] = enabled_skills
                spec["rails"] = [{
                    "type": "skill_use",
                    "params": skill_params,
                }]
            return spec

        spec = TeamAgentSpec.model_validate({
            "agents": {
                "leader": model_spec(model_routing.leader_model),
                "teammate": model_spec(model_routing.coding_model),
            },
            "model_router": model_routing.model_router,
            "transport": {"type": "inprocess"},
            "storage": {"type": "memory"},
            "team_name": f"devopspilot-exec-{team_runtime_id}",
            "lifecycle": "temporary",
            "teammate_mode": "build_mode",
            "spawn_mode": "inprocess",
            "leader": {
                "member_name": "devops_leader",
                "display_name": "DevOps Leader",
                "persona": (
                    "You are DevOpsPilot's software-delivery leader. "
                    "Work only in the repository workspace given by the task. "
                    "Use a strict sequential two-specialist protocol. First build the "
                    "team and spawn only coding_agent with "
                    f"model_name={model_routing.coding_model!r}. Wait until coding_agent "
                    "sends concrete patch and test evidence. Only then spawn review_agent "
                    "with "
                    f"model_name={model_routing.review_model!r}. The reviewer must "
                    "independently inspect the actual working tree and re-run verification. "
                    "Do NOT use create_task, claim_task, update_task, task-board completion "
                    "state, or manual shutdown_member as completion gates. Those runtime "
                    "states are advisory only. Do not repeatedly poll idle members. "
                    "After review_agent sends an explicit APPROVE or REJECT verdict, "
                    "immediately produce one final leader response and stop. "
                    "Never modify forbidden files. Never push or create remote PRs. "
                    "Do not commit; DevOpsPilot performs deterministic validation and "
                    "creates the commit after the team returns."
                ),
            },
        })

        query = self._build_query(
            task,
            workspace,
            coding_model=model_routing.coding_model,
            review_model=model_routing.review_model,
        )

        print(
            "DEVOPSPILOT_PHASE=agentteam.start "
            f"leader={model_routing.leader_model} "
            f"coding={model_routing.coding_model} "
            f"review={model_routing.review_model}"
        )
        capture = OpenJiuwenTrajectoryCapture(
            task_id=task.work_item.item_id,
            repository=task.repository.full_name,
            exporter="file",
            traces_dir=tempfile.mkdtemp(prefix="devopspilot_otel_"),
        )
        capture.start()
        capture_result = None
        runtime_timed_out = False
        await Runner.start()
        try:
            async with asyncio.timeout(self._completion_timeout):
                async for _chunk in Runner.run_agent_team_streaming(
                    agent_team=spec,
                    inputs={"query": query},
                    session=(
                        f"delivery-{_runtime_slug(task.repository.repository_id)}-"
                        f"{team_runtime_id}"
                    ),
                ):
                    pass
        except TimeoutError:
            # OpenJiuwen AgentTeam can currently finish useful coding/review work
            # while its streaming lifecycle remains open. Treat this as runtime
            # degradation, not task success. Deterministic postconditions below
            # still decide whether the software-engineering result is acceptable.
            runtime_timed_out = True
            print(
                "DEVOPSPILOT_RUNTIME_DEGRADED=agentteam_timeout "
                f"timeout_seconds={self._completion_timeout}"
            )
        finally:
            try:
                await Runner.stop()
            finally:
                try:
                    capture_result = capture.drain()
                finally:
                    capture.close()
        print("DEVOPSPILOT_PHASE=agentteam.complete")
        if capture_result is None or capture_result.trajectory is None:
            raise RuntimeError(
                "OpenJiuwen execution completed without a canonical trajectory"
            )
        runtime_metrics = trajectory_runtime_metrics(capture_result.trajectory)
        skill_tool_calls = sum(
            1
            for event in capture_result.trajectory.events
            if getattr(event.kind, "value", str(event.kind)) == "tool"
            and "skill" in event.name.lower()
        )
        print(
            "DEVOPSPILOT_PHASE=trajectory.complete "
            f"id={capture_result.trajectory.trajectory_id} "
            f"model_calls={runtime_metrics['model_calls']} "
            f"tool_calls={runtime_metrics['tool_calls']}"
        )

        await self._clean_runtime_artifacts(workspace)
        changed_paths = await self._validate_paths(workspace)
        diff = (await _run("git", "diff", "HEAD", "--", ".", cwd=workspace.path))[1]

        execution_metadata = {
            "workspace_path": str(workspace.path),
            "base_commit": workspace.base_commit,
            "execution_id": execution_id,
            "leader_model": model_routing.leader_model,
            "coding_model": model_routing.coding_model,
            "review_model": model_routing.review_model,
            "model_router_names": ",".join(
                model_routing.model_router["model_names"]
            ),
            "changed_paths": ",".join(sorted(changed_paths)),
            "trajectory_id": capture_result.trajectory.trajectory_id,
            "trajectory_event_count": str(len(capture_result.trajectory.events)),
            "model_calls": str(runtime_metrics["model_calls"]),
            "tool_calls": str(runtime_metrics["tool_calls"]),
            "skill_tool_calls": str(skill_tool_calls),
            "input_tokens": str(runtime_metrics["input_tokens"]),
            "output_tokens": str(runtime_metrics["output_tokens"]),
            "capture_issues": str(len(capture_result.issues)),
            "skills_dir": configured_skills_dir,
            "enabled_skills": ",".join(enabled_skills),
            "runtime_degraded": "true" if runtime_timed_out else "false",
            "runtime_degradation_reason": (
                "agentteam_timeout" if runtime_timed_out else ""
            ),
        }

        if not diff.strip():
            raise OpenJiuwenExecutionError(
                "AgentTeam completed without producing a code change",
                metadata=execution_metadata,
            )

        test_command = workspace.metadata.get("test_command", "").strip()
        test_summary = ""

        # Shell execution is confined to the workspace and is only used for
        # benchmark/repository-owned verification commands. Secrets are never
        # interpolated into this command.
        if test_command:
            print("DEVOPSPILOT_PHASE=verification.start")
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
                raise OpenJiuwenExecutionError(
                    f"Independent verification failed ({proc.returncode}):\n{test_summary}",
                    metadata=execution_metadata,
                    test_summary=test_summary,
                )
            print("DEVOPSPILOT_PHASE=verification.complete")

        # Verification commands can create interpreter/test caches or, more
        # importantly, mutate repository files after the pre-test path gate.
        # Remove only known ephemeral artifacts, then enforce the path policy
        # again so the commit/publisher observes a clean, still-constrained
        # workspace.
        await self._clean_runtime_artifacts(workspace)
        changed_paths = await self._validate_paths(workspace)

        allowed = {
            x for x in workspace.metadata.get("allowed_paths", "").split(",") if x
        }
        if allowed:
            await _run("git", "add", "--", *sorted(allowed), cwd=workspace.path)
        else:
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
        print(f"DEVOPSPILOT_PHASE=commit.complete sha={commit_sha}")

        return ExecutionResult(
            source_branch=workspace.source_branch,
            commit_sha=commit_sha,
            summary=(
                f"OpenJiuwen AgentTeam completed work item {task.work_item.item_id}; "
                "independent verification passed and a local commit was created."
            ),
            published=False,
            test_summary=test_summary.strip(),
            metadata=execution_metadata,
        )

    async def _clean_runtime_artifacts(
        self,
        workspace: ExecutionWorkspace,
    ) -> None:
        """Remove only untracked interpreter/test cache artifacts.

        Tracked files are never ignored or deleted by this cleanup.
        """
        raw = (await _run(
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            cwd=workspace.path,
        ))[1]
        for relative in (line.strip() for line in raw.splitlines() if line.strip()):
            path = Path(relative)
            parts = set(path.parts)
            ephemeral = (
                "__pycache__" in parts
                or ".pytest_cache" in parts
                or path.suffix == ".pyc"
            )
            if not ephemeral:
                continue
            target = workspace.path / path
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            elif target.exists():
                target.unlink()

    async def _validate_paths(
        self,
        workspace: ExecutionWorkspace,
    ) -> set[str]:
        allowed = {
            x for x in workspace.metadata.get("allowed_paths", "").split(",") if x
        }
        forbidden = {
            x for x in workspace.metadata.get("forbidden_paths", "").split(",") if x
        }

        tracked = (await _run(
            "git",
            "diff",
            "--name-only",
            "HEAD",
            "--",
            ".",
            cwd=workspace.path,
        ))[1]
        untracked = (await _run(
            "git",
            "ls-files",
            "--others",
            "--exclude-standard",
            cwd=workspace.path,
        ))[1]
        paths = {
            line.strip()
            for line in (tracked + "\n" + untracked).splitlines()
            if line.strip()
        }

        if forbidden & paths:
            raise RuntimeError(
                f"AgentTeam modified forbidden paths: {sorted(forbidden & paths)}"
            )
        if allowed and not paths.issubset(allowed):
            raise RuntimeError(
                f"AgentTeam modified paths outside allow-list: {sorted(paths - allowed)}"
            )

        max_changed = workspace.metadata.get("max_changed_files", "").strip()
        if max_changed and len(paths) > int(max_changed):
            raise RuntimeError(
                f"AgentTeam changed {len(paths)} files; max_changed_files={max_changed}"
            )
        return paths

    @staticmethod
    def _build_query(
        task: DeliveryTask,
        workspace: ExecutionWorkspace,
        *,
        coding_model: str,
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
- Enabled Skills: {workspace.metadata.get("enabled_skills", "(none)")}
- Skills directory: {workspace.metadata.get("skills_dir", "(none)")}
- If a relevant Skill is enabled, invoke and follow it before choosing a repair.
- Do not commit, push, or modify anything outside {workspace.path}
- Use sequential dynamic delegation, not a task-board workflow.
- Build the team, then spawn ONLY coding_agent first with model_name={coding_model!r}.
- coding_agent must implement the minimal patch, run tests, and send the leader
  the actual diff/test evidence. It must not create/update/claim task-board tasks.
- After receiving coding evidence, spawn review_agent with
  model_name={review_model!r}. Do not spawn the reviewer before coding finishes.
- review_agent must independently inspect the actual diff, re-run the test
  command, and send one explicit APPROVE or REJECT verdict. It must not modify files.
- Do not use create_task, view_task, claim_task, task completion state, or
  shutdown_member to decide whether the delivery is done.
- When the reviewer verdict arrives, the leader must immediately return its
  final response and stop; no extra polling, acknowledgements, or shutdown loop.
- The leader must leave the verified working-tree changes in place for
  DevOpsPilot to validate and commit.
""".strip()
