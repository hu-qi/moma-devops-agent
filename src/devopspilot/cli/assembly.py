"""Service and adapter assembly for DevOpsPilot CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from devopspilot.adapters.git.auth import build_clone_auth_args
from devopspilot.contracts.delivery import (
    DeliveryState,
    DeliveryVerifier,
    TaskExecutor,
)
from devopspilot.contracts.providers import CIProvider, SCMProvider
from devopspilot.contracts.state import DeliveryStateStore
from devopspilot.orchestration.delivery_loop import DeliveryLoop
from devopspilot.orchestration.service import DeliveryOrchestrator
from devopspilot.orchestration.verifier import StandardDeliveryVerifier
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore


@dataclass(frozen=True, slots=True)
class AppConfig:
    db_path: Path
    provider: str = "mock"
    default_target_branch: str = "main"
    execution_mode: str = "single_agent"
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    test_command: str = ""
    require_review: bool = True
    required_checks: tuple[str, ...] = ()
    extra_metadata: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AppConfig:
        db = Path(data.get("db_path", ".devopspilot/state.db"))
        return cls(
            db_path=db,
            provider=str(data.get("provider", "mock")),
            default_target_branch=str(data.get("default_target_branch", "main")),
            execution_mode=str(data.get("execution_mode", "single_agent")),
            allowed_paths=tuple(data.get("allowed_paths", ())),
            forbidden_paths=tuple(data.get("forbidden_paths", ())),
            test_command=str(data.get("test_command", "")),
            require_review=bool(data.get("require_review", True)),
            required_checks=tuple(data.get("required_checks", ())),
            extra_metadata=dict(data.get("extra_metadata", {})),
        )


# C08: trusted delivery configuration is supplied by the operator through the
# environment (never from untrusted Issue content) and flows into
# task.metadata -> workspace.metadata, where the executor, CI aggregator and
# verifier actually enforce it.
_TRUSTED_CONFIG_ENV: tuple[tuple[str, str], ...] = (
    ("test_command", "DEVOPSPILOT_TEST_COMMAND"),
    ("allowed_paths", "DEVOPSPILOT_ALLOWED_PATHS"),
    ("forbidden_paths", "DEVOPSPILOT_FORBIDDEN_PATHS"),
    ("required_checks", "DEVOPSPILOT_REQUIRED_CHECKS"),
)


def load_trusted_delivery_config(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Load operator-supplied trusted config into task metadata form.

    Returns a dict suitable for merging into task_metadata. Values mirror the
    keys the executor and delivery loop already consume: test_command,
    allowed_paths (comma-separated), forbidden_paths (comma-separated),
    required_checks (comma-separated), require_review ("true"/"false").
    """
    source = os.environ if env is None else env
    config: dict[str, str] = {}
    for key, var in _TRUSTED_CONFIG_ENV:
        value = source.get(var, "").strip()
        if value:
            config[key] = value
    require_review = source.get("DEVOPSPILOT_REQUIRE_REVIEW", "").strip().lower()
    if require_review in {"true", "false"}:
        config["require_review"] = require_review
    return config


def assemble_orchestrator(
    config: AppConfig,
    *,
    scm: SCMProvider | None = None,
    ci: CIProvider | None = None,
    executor: TaskExecutor | None = None,
    verifier: DeliveryVerifier | None = None,
    store: DeliveryStateStore | None = None,
) -> DeliveryOrchestrator:
    """Assemble a runnable DeliveryOrchestrator from config with pluggable components."""
    # Ensure database parent directory exists
    config.db_path.parent.mkdir(parents=True, exist_ok=True)
    state_store = store or SQLiteDeliveryStateStore(config.db_path)
    deliv_verifier = verifier or StandardDeliveryVerifier()

    if scm is None or ci is None or executor is None:
        raise ValueError("scm, ci, and executor adapters must be supplied for orchestrator assembly")

    loop = DeliveryLoop(
        scm=scm,
        ci=ci,
        executor=executor,
        verifier=deliv_verifier,
    )

    # C11: durable remediation control plane so resume() can drive the full
    # CI-failure loop (RCA -> budget reserve -> same-branch repair -> CI
    # rerun -> verify) without resetting the attempt budget on restart.
    control_plane = None
    try:
        from devopspilot.adapters.openjiuwen.remediation import OpenJiuwenRemediationExecutor
        from devopspilot.orchestration.control_plane import (
            AutonomousDeliveryControlPlane,
            RuleBasedCIFailureAnalyzer,
        )
        from devopspilot.persistence.remediation_ledger import SQLiteRemediationLedger

        remediation_executor = OpenJiuwenRemediationExecutor(executor)
        ledger = SQLiteRemediationLedger(config.db_path.parent / "remediation.db")
        control_plane = AutonomousDeliveryControlPlane(
            ci=ci,
            analyzer=RuleBasedCIFailureAnalyzer(),
            remediator=remediation_executor,
            ledger=ledger,
        )
    except Exception:
        control_plane = None

    return DeliveryOrchestrator(loop=loop, store=state_store, control_plane=control_plane)


DEFAULT_MOMA_API_BASE = "https://zhenze-huhehaote.cmecloud.cn/v1"
DEFAULT_MOMA_MODEL = "deepseek-v4.1-flash"
DEFAULT_MOMA_CODING_MODEL = "Qwen3-32B"
DEFAULT_MOMA_REVIEW_MODEL = "deepseek-v4.1-flash"


def setup_model_environment() -> bool:
    """Ensure MoMA model environment variables are properly wired with native MoMA defaults."""
    moma_key = os.environ.get("MOMA_API_KEY", "").strip() or os.environ.get("DEEPSEEK_API_KEY", "").strip()

    if moma_key:
        os.environ["MOMA_API_KEY"] = moma_key

    if moma_key and not os.environ.get("MOMA_API_BASE"):
        os.environ["MOMA_API_BASE"] = os.environ.get("MOMA_BASE_URL", "").strip() or DEFAULT_MOMA_API_BASE

    if moma_key and not os.environ.get("MOMA_MODEL"):
        os.environ["MOMA_MODEL"] = DEFAULT_MOMA_MODEL

    if moma_key and not os.environ.get("MOMA_CODING_MODEL"):
        os.environ["MOMA_CODING_MODEL"] = os.environ.get("MOMA_MODEL", DEFAULT_MOMA_CODING_MODEL)

    if moma_key and not os.environ.get("MOMA_REVIEW_MODEL"):
        os.environ["MOMA_REVIEW_MODEL"] = os.environ.get("MOMA_MODEL", DEFAULT_MOMA_REVIEW_MODEL)

    return bool(moma_key)


def assemble_live_orchestrator(
    config: AppConfig,
    repo_full_name: str,
    *,
    store: DeliveryStateStore | None = None,
) -> DeliveryOrchestrator:
    """Assemble a full live DeliveryOrchestrator with real SCM, CI, and AI Executor."""
    from devopspilot.adapters.git import AutoCloningWorktreeWorkspaceProvider, GitChangePublisher
    from devopspilot.orchestration.execution import PublishingTaskExecutor

    provider = config.provider.lower()
    has_model = setup_model_environment()

    # 1. Setup SCM, CI, and Remote Clone URL
    if provider == "atomgit":
        from devopspilot.adapters.atomgit.client import AtomGitHTTPClient
        from devopspilot.adapters.atomgit.scm import AtomGitSCMProvider
        from devopspilot.adapters.atomgit.ci import AtomGitCIProvider

        token = os.environ.get("ATOMGIT_TOKEN", "").strip()
        client = AtomGitHTTPClient(token=token if token else None)
        scm = AtomGitSCMProvider(client)
        ci = AtomGitCIProvider(client)
        # C06: token goes via http.extraHeader git config, never the URL
        clone_url = f"https://atomgit.com/{repo_full_name}.git"
        clone_auth_args = build_clone_auth_args(provider, token)
    elif provider == "github":
        from devopspilot.adapters.github.client import GitHubHTTPClient
        from devopspilot.adapters.github.scm import GitHubSCMProvider
        from devopspilot.adapters.github.ci import GitHubCIProvider

        token = os.environ.get("GITHUB_TOKEN", "").strip()
        gh_client = GitHubHTTPClient(token=token)
        scm = GitHubSCMProvider(gh_client)
        ci = GitHubCIProvider(gh_client)
        # C06: token goes via http.extraHeader git config, never the URL
        clone_url = f"https://github.com/{repo_full_name}.git"
        clone_auth_args = build_clone_auth_args(provider, token)
    else:
        raise ValueError(f"Unsupported live provider for automated assembly: {provider}")

    # 2. Setup Workspace Provider & Change Publisher
    workspace_provider = AutoCloningWorktreeWorkspaceProvider(
        repository_id=repo_full_name,
        clone_url=clone_url,
        clone_auth_args=clone_auth_args,
    )
    publisher = GitChangePublisher(remote="origin")

    # 3. Setup Task Executor (OpenJiuwen with AI, wrapped with PublishingTaskExecutor)
    if not has_model:
        raise RuntimeError("No MOMA_API_KEY or DEEPSEEK_API_KEY configured for live AI execution.")

    from devopspilot.adapters.openjiuwen.executor import OpenJiuwenTaskExecutor
    from devopspilot.adapters.moma import MoMAProvider
    from devopspilot.trajectory.persistent_store import FileTrajectoryStore

    maas = MoMAProvider.from_env()
    # C10: one canonical trajectory store shared by executor (saves evidence)
    # and verifier (loads and cross-checks it) — evidence is real disk state.
    trajectory_store = FileTrajectoryStore(config.db_path.parent / "trajectories")
    inner_executor = OpenJiuwenTaskExecutor(
        workspace_provider=workspace_provider,
        maas_provider=maas,
        trajectory_store=trajectory_store,
    )
    executor = PublishingTaskExecutor(inner_executor, publisher)

    # 4. Assemble
    return assemble_orchestrator(
        config,
        scm=scm,
        ci=ci,
        executor=executor,
        verifier=StandardDeliveryVerifier(trajectory_store=trajectory_store),
        store=store,
    )
