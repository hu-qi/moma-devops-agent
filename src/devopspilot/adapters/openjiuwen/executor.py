"""OpenJiuwen-backed implementation of the DevOpsPilot TaskExecutor port."""

from __future__ import annotations

import asyncio
import hashlib
import os
import re
import shlex
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from devopspilot.contracts.delivery import DeliveryTask, ExecutionResult
from devopspilot.contracts.execution import (
    ExecutionWorkspace,
    WorkspaceProvider,
    ReviewResult,
    ReviewVerdict,
    ReviewGateError,
    enforce_review_gate,
)
from devopspilot.contracts.planning import ExecutionMode, ExecutionPlan
from devopspilot.routing.execution_planner import SingleAgentFirstPlanner
from devopspilot.orchestration.test_runner import (
    ControlledRunResult,
    EmptyVerificationCommandError,
    OracleTamperError,
    VerificationError,
    VerificationTimeoutError,
    run_controlled_command,
    verify_oracle_not_tampered,
)
from devopspilot.contracts.providers import MaaSProvider
from devopspilot.contracts.trajectory import DeliveryTrajectory
from devopspilot.evaluation.metrics import trajectory_runtime_metrics
from devopspilot.routing import AgentTeamModelPlanner, DeliveryTaskProfiler
from devopspilot.trajectory import (
    OpenJiuwenCaptureResult,
    OpenJiuwenTrajectoryCapture,
)

from .lock_shim import apply_controlled_lock_shim, get_shim_state
from .model_router import build_team_model_routing


def _patch_openjiuwen_lock_manager() -> None:
    """Compatibility shim for tests explicitly requesting lock patching."""
    apply_controlled_lock_shim(force=True)


async def _safe_runner_stop(timeout: float = 10.0) -> None:
    """Defensively stop Runner without unconditionally mutating global lock behavior."""
    try:
        from openjiuwen.core.runner.runner import Runner

        stop_task = asyncio.create_task(Runner.stop())
        try:
            await asyncio.wait_for(asyncio.shield(stop_task), timeout=timeout)
        except asyncio.TimeoutError:
            print(
                f"DEVOPSPILOT_WARN: Runner.stop timed out after {timeout}s; proceeding with forced cleanup"
            )
            stop_task.cancel()
    except Exception as exc:
        print(f"DEVOPSPILOT_WARN: Runner.stop encountered error: {exc}")


def _safe_capture_drain(
    capture: OpenJiuwenTrajectoryCapture,
) -> OpenJiuwenCaptureResult | None:
    try:
        return capture.drain()
    except Exception as exc:
        print(f"DEVOPSPILOT_WARN: capture.drain encountered error: {exc}")
        return None


def _safe_capture_close(capture: OpenJiuwenTrajectoryCapture) -> None:
    try:
        capture.close()
    except Exception as exc:
        print(f"DEVOPSPILOT_WARN: capture.close encountered error: {exc}")


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
        trajectory_store=None,
    ) -> None:
        self._workspace_provider = workspace_provider
        self._maas_provider = maas_provider
        self._task_profiler = task_profiler or DeliveryTaskProfiler()
        self._max_iterations = max_iterations
        self._completion_timeout = completion_timeout
        # C10: canonical trajectory persistence — evidence must be saved to
        # disk, not just claimed in metadata.
        self._trajectory_store = trajectory_store

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
        import time
        execution_started = time.monotonic()
        try:
            from openjiuwen.agent_teams import TeamAgentSpec
            from openjiuwen.core.runner import Runner
        except (ImportError, ModuleNotFoundError) as mod_err:
            print(f"DEVOPSPILOT_NOTICE: OpenJiuwen package not installed ({mod_err}).")
            print("DEVOPSPILOT_NOTICE: Seamlessly routing to MoMA platform Native Agent Executor...")
            return await self._execute_with_moma_native(task, workspace)

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

        # Resolve or generate structured execution plan (Single Agent First)
        raw_plan = workspace.metadata.get("execution_plan") or task.metadata.get("execution_plan")
        if raw_plan:
            try:
                execution_plan = ExecutionPlan.from_json(raw_plan)
            except Exception:
                execution_plan = SingleAgentFirstPlanner().plan(task)
        else:
            override_m = workspace.metadata.get("execution_mode") or task.metadata.get("execution_mode")
            execution_plan = SingleAgentFirstPlanner().plan(task, override_mode=override_m)

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
                **(
                    # C08: team mode requires an actual teammate; single_agent runs
                    # a one-agent team (leader only) so mode is a real behavioral
                    # difference, not just plan metadata.
                    {}
                    if execution_plan.mode is ExecutionMode.SINGLE_AGENT
                    else {"teammate": model_spec(model_routing.coding_model)}
                ),
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
                    (
                        "You are DevOpsPilot's solo software-delivery agent (single_agent mode). "
                        "Implement the change yourself and then self-verify; an independent "
                        "review pass still runs afterwards outside this agent. "
                        if execution_plan.mode is ExecutionMode.SINGLE_AGENT
                        else
                        "You are DevOpsPilot's software-delivery leader. "
                        "Work only in the repository workspace given by the task. "
                        "Use a strict sequential two-specialist protocol. First build the "
                        "team and spawn only coding_agent with "
                        f"model_name={model_routing.coding_model!r}. Wait until coding_agent "
                        "sends concrete patch and test evidence. Only then spawn review_agent "
                        "with "
                        f"model_name={model_routing.review_model!r}. The reviewer must "
                        "independently inspect the actual working tree and re-run verification. "
                    )
                    + "Do NOT use create_task, claim_task, update_task, task-board completion "
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
        _patch_openjiuwen_lock_manager()
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
                await _safe_runner_stop(timeout=10.0)
            finally:
                try:
                    capture_result = _safe_capture_drain(capture)
                finally:
                    _safe_capture_close(capture)
        print("DEVOPSPILOT_PHASE=agentteam.complete")
        if capture_result is None or capture_result.trajectory is None:
            if runtime_timed_out:
                fallback_trajectory = DeliveryTrajectory(
                    trajectory_id=f"fallback-{task.work_item.item_id}",
                    task_id=task.work_item.item_id,
                    repository=task.repository.full_name,
                    events=(),
                )
                capture_result = OpenJiuwenCaptureResult(
                    trajectory=fallback_trajectory,
                    issues=(
                        {
                            "kind": "degraded_capture",
                            "reason": "agentteam_timeout_or_capture_failure",
                        },
                    ),
                )
            else:
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

        # C10: persist the canonical trajectory as real evidence. A fallback
        # trajectory (degraded capture) is still saved but is marked via its
        # id so the verifier rejects it as incomplete evidence.
        if self._trajectory_store is not None:
            try:
                saved_path = await self._trajectory_store.save(capture_result.trajectory)
                print(f"DEVOPSPILOT_PHASE=trajectory.saved path={saved_path}")
            except Exception as exc:
                raise OpenJiuwenExecutionError(
                    f"Failed to persist canonical trajectory evidence: {exc}",
                    metadata={"trajectory_id": capture_result.trajectory.trajectory_id},
                ) from exc

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
            "execution_mode": execution_plan.mode.value,
            "execution_plan": execution_plan.to_json(),
            "execution_rationale": execution_plan.rationale,
            "runtime_degraded": "true" if runtime_timed_out else "false",
            "runtime_degradation_reason": (
                "agentteam_timeout" if runtime_timed_out else ""
            ),
            # C14: latency recorded into the same run for benchmarking
            "elapsed_seconds": f"{time.monotonic() - execution_started:.3f}",
        }

        if not diff.strip():
            raise OpenJiuwenExecutionError(
                "AgentTeam completed without producing a code change",
                metadata=execution_metadata,
            )

        test_command = workspace.metadata.get("test_command", "").strip()
        require_verification = (
            workspace.metadata.get("require_verification", "").lower() == "true"
            or task.metadata.get("require_verification", "").lower() == "true"
        )
        test_summary = ""

        # Enforce non-empty verification command if verification is explicitly required
        if require_verification and not test_command:
            raise OpenJiuwenExecutionError(
                "Verification is required but test_command is empty",
                metadata=execution_metadata,
            )

        # Oracle tamper check before test execution
        forbidden_list = tuple(
            x.strip() for x in workspace.metadata.get("forbidden_paths", "").split(",") if x.strip()
        )
        if forbidden_list:
            try:
                verify_oracle_not_tampered(workspace.path, forbidden_list)
            except OracleTamperError as exc:
                raise OpenJiuwenExecutionError(
                    str(exc),
                    metadata=execution_metadata,
                ) from exc

        # Shell execution is confined to the workspace with timeout and process group cleanup
        if test_command:
            print("DEVOPSPILOT_PHASE=verification.start")
            timeout_sec = float(workspace.metadata.get("test_timeout_seconds", 60.0))
            try:
                run_res = await run_controlled_command(
                    test_command,
                    cwd=workspace.path,
                    timeout_seconds=timeout_sec,
                    require_non_empty=require_verification,
                )
            except VerificationError as exc:
                raise OpenJiuwenExecutionError(
                    f"Verification execution error: {exc}",
                    metadata=execution_metadata,
                ) from exc

            test_summary = run_res.combined_output[-4000:]
            if run_res.returncode != 0:
                raise OpenJiuwenExecutionError(
                    f"Independent verification failed ({run_res.returncode}):\n{test_summary}",
                    metadata=execution_metadata,
                    test_summary=test_summary,
                )
            print("DEVOPSPILOT_PHASE=verification.complete")

        # Verification commands can create interpreter/test caches or mutate repository files.
        # Ensure forbidden oracle files were not altered during test run.
        if forbidden_list:
            try:
                verify_oracle_not_tampered(workspace.path, forbidden_list)
            except OracleTamperError as exc:
                raise OpenJiuwenExecutionError(
                    f"Post-test check failed: {exc}",
                    metadata=execution_metadata,
                ) from exc

        # Remove only known ephemeral artifacts, then enforce the path policy
        # again so the commit/publisher observes a clean, still-constrained
        # workspace.
        await self._clean_runtime_artifacts(workspace)
        changed_paths = await self._validate_paths(workspace)
        diff_after_test = (await _run("git", "diff", "HEAD", "--", ".", cwd=workspace.path))[1]

        # Enforce review gate policy if required by task metadata or configuration
        review_result: ReviewResult | None = getattr(workspace, "review_result", None)
        if review_result is None and "review_result" in workspace.metadata:
            import json
            try:
                raw_rev = json.loads(workspace.metadata["review_result"])
                review_result = ReviewResult(
                    reviewer_id=raw_rev.get("reviewer_id", "reviewer"),
                    verdict=ReviewVerdict(raw_rev.get("verdict", "rejected")),
                    diff_digest=raw_rev.get("diff_digest", ""),
                    summary=raw_rev.get("summary", ""),
                    metadata=raw_rev.get("metadata", {}),
                )
            except Exception:
                review_result = None

        require_review = (
            workspace.metadata.get("require_review", "").lower() == "true"
            or task.metadata.get("require_review", "").lower() == "true"
        )
        if require_review:
            try:
                enforce_review_gate(
                    review=review_result,
                    current_diff=diff_after_test,
                    require_review=True,
                )
            except ReviewGateError as exc:
                raise OpenJiuwenExecutionError(
                    f"Review gate rejected commit: {exc}",
                    metadata={
                        **execution_metadata,
                        "review_verdict": review_result.verdict.value if review_result else "missing",
                        "review_gate_error": str(exc),
                    },
                ) from exc

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
            review=review_result,
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
        # C09: shared path policy — normalize config defensively and validate
        # against real workspace paths (blocks absolute / .. / symlink escape).
        from devopspilot.orchestration.path_policy import (
            normalize_policy_paths,
            validate_changed_paths,
        )

        allowed, forbidden = normalize_policy_paths(
            workspace.metadata.get("allowed_paths", ""),
            workspace.metadata.get("forbidden_paths", ""),
            workspace_path=workspace.path,
        )

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

        try:
            validate_changed_paths(paths, allowed=allowed, forbidden=forbidden)
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

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
        industry_section = ""
        if task.industry_pack is not None:
            try:
                from devopspilot.industry import build_industry_context
                industry_section = f"\n\n{build_industry_context(task.industry_pack)}"
            except Exception:
                pass

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
  DevOpsPilot to validate and commit.{industry_section}
""".strip()

    async def _execute_with_moma_native(
        self,
        task: DeliveryTask,
        workspace: ExecutionWorkspace,
    ) -> ExecutionResult:
        """Native MoMA-driven autonomous agent executor when openjiuwen core package is omitted.

        C04: this fallback is disabled by default. It must be explicitly enabled
        with DEVOPSPILOT_ENABLE_NATIVE_FALLBACK=1 after the pipeline meets the
        Stage-2 gate criteria; silent automatic degradation is forbidden.
        """
        if os.environ.get("DEVOPSPILOT_ENABLE_NATIVE_FALLBACK", "").strip() != "1":
            raise RuntimeError(
                "Native MoMA fallback executor is disabled (Stage2/C04). "
                "Set DEVOPSPILOT_ENABLE_NATIVE_FALLBACK=1 to explicitly opt in, "
                "or install the openjiuwen package for the controlled pipeline."
            )
        import json
        from devopspilot.adapters.moma.client import MoMAClient
        from devopspilot.contracts.trajectory import (
            DeliveryTrajectory,
            TrajectoryEvent,
            TrajectoryEventKind,
        )
        from devopspilot.utils.model_text import (
            extract_json_payload,
            sanitize_file_content,
            strip_think_tags,
        )

        api_key = _required_env("MOMA_API_KEY")
        api_base = _required_env("MOMA_API_BASE")
        coding_model = (
            os.environ.get("MOMA_CODING_MODEL")
            or os.environ.get("MOMA_MODEL")
            or "Qwen3-32B"
        )
        review_model = (
            os.environ.get("MOMA_REVIEW_MODEL")
            or os.environ.get("MOMA_MODEL")
            or "deepseek-v4.1-flash"
        )

        client = MoMAClient(api_key=api_key, api_base=api_base, default_model=coding_model)

        # C04: path boundary — every model-provided file must resolve inside the workspace.
        def _safe_workspace_file(rel_path: str) -> Path | None:
            if not rel_path or rel_path.strip() != rel_path:
                return None
            candidate = (workspace.path / rel_path).resolve()
            try:
                candidate.relative_to(workspace.path.resolve())
            except ValueError:
                return None
            # Forbid overwriting existing tracked files without explicit opt-in
            forbidden_names = {".git", ".env", ".github", "devopspilot.db"}
            if any(part in forbidden_names for part in candidate.relative_to(workspace.path.resolve()).parts):
                return None
            return candidate

        # 1. Collect workspace context
        ls_files_out = (await _run("git", "ls-files", cwd=workspace.path))[1]
        existing_files = [f.strip() for f in ls_files_out.splitlines() if f.strip()]

        readme_path = workspace.path / "README.md"
        readme_content = ""
        if readme_path.exists():
            try:
                readme_content = readme_path.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass

        # 2. Invoke MoMA Coding Model
        sys_prompt = (
            "You are an expert DevOps and Software Engineering Agent operating on China Mobile Cloud (MoMA) platform.\n"
            "Your task is to analyze requirements, inspect the repository files, and provide concrete code modifications.\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. You must return ONLY a single JSON object with this exact structure:\n"
            "{\n"
            '  "summary": "Brief human-readable summary of the implementation",\n'
            '  "files": [\n'
            '    {\n'
            '      "path": "relative/file/path",\n'
            '      "content": "Full source code content of the file"\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "2. Do NOT include any <think> tags, reasoning traces, or explanations in your output.\n"
            "3. Do NOT include the JSON structure itself or any markdown fences inside the file 'content'.\n"
            "4. Start your response directly with { and end with }."
        )

        user_prompt = (
            f"Repository: {task.repository.full_name}\n"
            f"Work item #{task.work_item.item_id}: {task.work_item.title}\n\n"
            f"Work item description:\n{task.work_item.body}\n\n"
            f"Existing repository files:\n"
            + ("\n".join(existing_files) if existing_files else "(empty repository)")
            + (f"\n\nExisting README snippet:\n{readme_content}" if readme_content else "")
            + "\n\nPlease generate the required files or updates to resolve this work item completely."
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]

        print(f"      [MoMA Native Agent] Coding turn: invoking {coding_model} via MoMA...")
        resp = await asyncio.to_thread(client.chat_completion, messages, model=coding_model)
        content = resp["choices"][0]["message"]["content"].strip()
        usage = resp.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # Parse output safely and extract file operations.
        # C04 fail-closed: unparseable model output must NOT be silently turned
        # into a fabricated markdown "delivery" file counted as task completion.
        try:
            parsed = extract_json_payload(content)
            if not isinstance(parsed, dict):
                raise ValueError("model output is not a JSON object")
        except Exception as parse_err:
            return ExecutionResult(
                source_branch=workspace.source_branch,
                commit_sha="",
                summary=f"Native execution aborted: model output unparseable ({parse_err}).",
                published=False,
                test_summary="No tests executed — coding output failed JSON validation gate.",
                review=ReviewResult(
                    reviewer_id="moma-quality-gate",
                    verdict=ReviewVerdict.REJECTED,
                    diff_digest="sha256:empty",
                    summary="Fail-closed: no files written from unparseable model output.",
                ),
                metadata={
                    "execution_mode": "moma_native_fallback",
                    "gate": "json_parse",
                    "gate_outcome": "rejected",
                },
            )

        files_to_write = parsed.get("files", [])
        written_any = False
        for file_spec in files_to_write:
            rel_path = file_spec.get("path")
            if not rel_path:
                continue
            # C04 path boundary: reject traversal and forbidden targets
            target_file = _safe_workspace_file(str(rel_path))
            if target_file is None:
                print(f"      [MoMA Native Agent] Path boundary: rejected unsafe file path {rel_path!r}")
                continue
            fcontent = sanitize_file_content(str(file_spec.get("content", "")), file_path=str(rel_path))
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(fcontent, encoding="utf-8")
            written_any = True

        if not written_any:
            return ExecutionResult(
                source_branch=workspace.source_branch,
                commit_sha="",
                summary=f"Native execution aborted: model produced no writable files for work item #{task.work_item.item_id}.",
                published=False,
                test_summary="No tests executed — no file changes passed the path-boundary gate.",
                review=ReviewResult(
                    reviewer_id="moma-quality-gate",
                    verdict=ReviewVerdict.REJECTED,
                    diff_digest="sha256:empty",
                    summary="Fail-closed: zero valid file writes; nothing to deliver.",
                ),
                metadata={
                    "execution_mode": "moma_native_fallback",
                    "gate": "path_boundary",
                    "gate_outcome": "rejected",
                },
            )

        # C09: shared gates — the native fallback must satisfy the SAME
        # trusted-config enforcement as the runtime executor: path policy,
        # oracle tamper checks, controlled test execution, and industry gates.
        from devopspilot.orchestration.path_policy import (
            normalize_policy_paths,
            validate_changed_paths,
        )
        from devopspilot.orchestration.test_runner import (
            OracleTamperError,
            run_controlled_command,
            verify_oracle_not_tampered,
        )
        from devopspilot.industry.gate_runner import IndustryGateRunner

        forbidden_list_native = tuple(
            x.strip() for x in workspace.metadata.get("forbidden_paths", "").split(",") if x.strip()
        )
        allowed_list_native = tuple(
            x.strip() for x in workspace.metadata.get("allowed_paths", "").split(",") if x.strip()
        )
        try:
            allowed_norm, forbidden_norm = normalize_policy_paths(
                ",".join(allowed_list_native),
                ",".join(forbidden_list_native),
                workspace_path=workspace.path,
            )
            changed_now = {
                p
                for p in (await _run("git", "status", "--porcelain", cwd=workspace.path))[1].splitlines()
                if p.strip()
            }
            changed_files = {line[3:].strip() for line in changed_now if line.strip()}
            validate_changed_paths(
                changed_files,
                allowed=allowed_norm,
                forbidden=forbidden_norm,
            )
        except Exception as policy_err:
            return ExecutionResult(
                source_branch=workspace.source_branch,
                commit_sha="",
                summary=f"Native execution blocked by path policy: {policy_err}",
                published=False,
                test_summary="No tests executed — changed paths rejected by shared path policy.",
                review=ReviewResult(
                    reviewer_id="moma-quality-gate",
                    verdict=ReviewVerdict.REJECTED,
                    diff_digest="sha256:empty",
                    summary=f"Fail-closed: path policy violation ({policy_err}).",
                ),
                metadata={
                    "execution_mode": "moma_native_fallback",
                    "gate": "path_policy",
                    "gate_outcome": "rejected",
                },
            )

        if forbidden_list_native:
            try:
                verify_oracle_not_tampered(workspace.path, forbidden_list_native)
            except OracleTamperError as tamper_err:
                return ExecutionResult(
                    source_branch=workspace.source_branch,
                    commit_sha="",
                    summary=f"Native execution blocked: oracle tampering detected ({tamper_err})",
                    published=False,
                    test_summary="No tests executed — forbidden oracle file was modified.",
                    review=ReviewResult(
                        reviewer_id="moma-quality-gate",
                        verdict=ReviewVerdict.REJECTED,
                        diff_digest="sha256:empty",
                        summary="Fail-closed: forbidden oracle file tampered before tests.",
                    ),
                    metadata={
                        "execution_mode": "moma_native_fallback",
                        "gate": "oracle_tamper",
                        "gate_outcome": "rejected",
                    },
                )

        # C09: industry gates must also bind the native fallback — a bound
        # pack's required gates run on the real workspace and a failure or
        # timeout blocks delivery exactly like the runtime executor path.
        industry_pack_native = task.industry_pack
        if industry_pack_native is None and task.metadata.get("industry_pack"):
            try:
                import json as _json
                from devopspilot.industry.loader import load_pack_from_dict
                raw_pack = task.metadata.get("industry_pack")
                data = _json.loads(raw_pack) if isinstance(raw_pack, str) else dict(raw_pack)
                industry_pack_native = load_pack_from_dict(data)
            except Exception:
                industry_pack_native = None
        if industry_pack_native is not None:
            gate_runner_native = IndustryGateRunner()
            gate_results = await gate_runner_native.run_gates(industry_pack_native, workspace.path)
            failed_required = [
                g for g in gate_results if g.required and not g.passed
            ]
            if failed_required:
                failed_names = ", ".join(f"{g.name}({g.message[:80]})" for g in failed_required)
                return ExecutionResult(
                    source_branch=workspace.source_branch,
                    commit_sha="",
                    summary=f"Native execution blocked by industry gate: {failed_names}",
                    published=False,
                    test_summary=f"Industry gates: {sum(1 for g in gate_results if g.passed)}/{len(gate_results)} passed.",
                    review=ReviewResult(
                        reviewer_id="moma-quality-gate",
                        verdict=ReviewVerdict.REJECTED,
                        diff_digest="sha256:empty",
                        summary=f"Fail-closed: required industry gate(s) failed — {failed_names}",
                    ),
                    metadata={
                        "execution_mode": "moma_native_fallback",
                        "gate": "industry",
                        "gate_outcome": "rejected",
                        "industry_gates_passed": "false",
                    },
                )

        test_command_native = workspace.metadata.get("test_command", "").strip()
        test_summary_native = ""
        if test_command_native:
            print("      [MoMA Native Agent] Verification: running controlled test command...")
            timeout_native = float(workspace.metadata.get("test_timeout_seconds", 60.0))
            try:
                run_native = await run_controlled_command(
                    test_command_native,
                    cwd=workspace.path,
                    timeout_seconds=timeout_native,
                    require_non_empty=False,
                )
                test_summary_native = run_native.combined_output[-4000:]
                if run_native.returncode != 0:
                    return ExecutionResult(
                        source_branch=workspace.source_branch,
                        commit_sha="",
                        summary=f"Native execution blocked: independent verification failed ({run_native.returncode}).",
                        published=False,
                        test_summary=test_summary_native,
                        review=ReviewResult(
                            reviewer_id="moma-quality-gate",
                            verdict=ReviewVerdict.REJECTED,
                            diff_digest="sha256:empty",
                            summary="Fail-closed: verification command failed.",
                        ),
                        metadata={
                            "execution_mode": "moma_native_fallback",
                            "gate": "verification",
                            "gate_outcome": "rejected",
                        },
                    )
                print("      [MoMA Native Agent] Verification: passed.")
            except Exception as verify_err:
                return ExecutionResult(
                    source_branch=workspace.source_branch,
                    commit_sha="",
                    summary=f"Native execution blocked: verification error ({verify_err})",
                    published=False,
                    test_summary="Verification could not be executed.",
                    review=ReviewResult(
                        reviewer_id="moma-quality-gate",
                        verdict=ReviewVerdict.REJECTED,
                        diff_digest="sha256:empty",
                        summary=f"Fail-closed: verification error ({verify_err}).",
                    ),
                    metadata={
                        "execution_mode": "moma_native_fallback",
                        "gate": "verification",
                        "gate_outcome": "rejected",
                    },
                )

        # 3. Stage changes and inspect diff
        await _run("git", "add", "-A", cwd=workspace.path)
        diff_out = (await _run("git", "diff", "--staged", cwd=workspace.path))[1]
        diff_digest = f"sha256:{hashlib.sha256(diff_out.encode('utf-8')).hexdigest()[:16]}"

        # 4. Review Gate with MoMA Review Model — C04 fail-closed:
        # verdict must come from strict parsing of the reviewer output,
        # never hardcoded; empty diff is auto-rejected.
        if not diff_out.strip():
            print("      [MoMA Native Agent] Quality gate: REJECTED (empty diff — no effective changes)")
            review_result = ReviewResult(
                reviewer_id="moma-quality-gate",
                verdict=ReviewVerdict.REJECTED,
                diff_digest=diff_digest,
                summary="Fail-closed: staged diff is empty; no effective change to review.",
            )
        else:
            print(f"      [MoMA Native Agent] Quality gate: invoking independent review ({review_model})...")
            rev_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an independent Code Reviewer on the MoMA platform. "
                        "Review the following git diff against the work item requirement. "
                        "Output JSON: {\"verdict\": \"approved\" | \"rejected\", \"summary\": \"review remarks\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Work item: {task.work_item.title}\nGit Diff:\n{diff_out[:4000]}",
                },
            ]
            rev_resp = await asyncio.to_thread(client.chat_completion, rev_messages, model=review_model)
            rev_usage = rev_resp.get("usage", {})
            prompt_tokens += rev_usage.get("prompt_tokens", 0)
            completion_tokens += rev_usage.get("completion_tokens", 0)

            # Strict verdict parsing — fail-closed on missing/invalid output
            rev_verdict = ReviewVerdict.REJECTED
            rev_summary = "Fail-closed: reviewer output missing or invalid JSON."
            try:
                rev_parsed = extract_json_payload(rev_resp["choices"][0]["message"]["content"])
                if isinstance(rev_parsed, dict) and isinstance(rev_parsed.get("verdict"), str):
                    verdict_value = rev_parsed["verdict"].strip().lower()
                    if verdict_value == "approved":
                        rev_verdict = ReviewVerdict.APPROVED
                    elif verdict_value == "rejected":
                        rev_verdict = ReviewVerdict.REJECTED
                    # any other value stays REJECTED
                    rev_summary = str(rev_parsed.get("summary", rev_summary)).strip() or rev_summary
            except Exception:
                pass

            review_result = ReviewResult(
                reviewer_id="moma-quality-gate",
                verdict=rev_verdict,
                diff_digest=diff_digest,
                summary=rev_summary,
            )

        if review_result.verdict is not ReviewVerdict.APPROVED:
            print(f"      [MoMA Native Agent] Quality gate: REJECTED — {review_result.summary}")
            return ExecutionResult(
                source_branch=workspace.source_branch,
                commit_sha="",
                summary=f"Native execution blocked by quality gate: {review_result.summary}",
                published=False,
                test_summary="No tests executed — changes rejected by independent review gate.",
                review=review_result,
                metadata={
                    "execution_mode": "moma_native_fallback",
                    "gate": "review",
                    "gate_outcome": "rejected",
                    "diff_digest": diff_digest,
                },
            )

        # 5. Create local commit
        commit_msg = f"fix: resolve work item #{task.work_item.item_id} - {task.work_item.title}"
        await _run(
            "git",
            "-c",
            "user.name=DevOpsPilot",
            "-c",
            "user.email=devopspilot@local",
            "commit",
            "-m",
            commit_msg,
            cwd=workspace.path,
        )
        commit_sha = (await _run("git", "rev-parse", "HEAD", cwd=workspace.path))[1].strip()

        traj = DeliveryTrajectory(
            trajectory_id=workspace.metadata.get("delivery_id", "default"),
            task_id=task.work_item.item_id,
            repository=task.repository.full_name,
            events=(
                TrajectoryEvent(
                    sequence=1,
                    kind=TrajectoryEventKind.ROUTING,
                    name="model.invoke",
                    status="success",
                    attributes={
                        "model": coding_model,
                        "input_tokens": prompt_tokens,
                        "output_tokens": completion_tokens,
                    },
                ),
            ),
        )

        # C10: the native fallback must persist the canonical trajectory to the
        # shared store and reference it from execution metadata — the verifier
        # loads the disk artifact and cross-checks the claim, so a fabricated
        # metadata-only trajectory can never pass verification.
        trajectory_id_native = ""
        trajectory_events_native = 0
        if self._trajectory_store is not None:
            try:
                saved_path = await self._trajectory_store.save(traj)
                trajectory_id_native = traj.trajectory_id
                trajectory_events_native = len(traj.events)
                print(f"      [MoMA Native Agent] Trajectory saved: {saved_path.name}")
            except Exception as traj_err:
                print(f"      [MoMA Native Agent] Trajectory save failed: {traj_err}")

        execution_metadata = {
            "workspace_path": str(workspace.path),
            "base_commit": workspace.base_commit,
            "model_calls": "2",
            "prompt_tokens": str(prompt_tokens),
            "completion_tokens": str(completion_tokens),
            "total_tokens": str(prompt_tokens + completion_tokens),
            "leader_model": coding_model,
            "coding_model": coding_model,
            "review_model": review_model,
            "execution_mode": "moma_native_fallback",
            "trajectory_id": trajectory_id_native,
            "trajectory_event_count": str(trajectory_events_native),
            "capture_issues": "0" if trajectory_id_native else "1",
            # C14: latency recorded into the same run for benchmarking
            "elapsed_seconds": f"{time.monotonic() - execution_started:.3f}",
        }

        raw_summary = parsed.get("summary", f"Resolved work item {task.work_item.item_id} via MoMA Agent.")
        cleaned_summary = strip_think_tags(str(raw_summary)).strip() or f"Resolved work item {task.work_item.item_id}"

        return ExecutionResult(
            source_branch=workspace.source_branch,
            commit_sha=commit_sha,
            summary=cleaned_summary,
            published=False,
            test_summary="MoMA native quality gate verification passed.",
            review=review_result,
            metadata=execution_metadata,
        )
