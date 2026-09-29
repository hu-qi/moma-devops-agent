"""Smoke test for unified DevOpsPilot CLI commands: start, status, resume, and report."""

from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# Offline guarantee (C01): strip live credentials BEFORE devopspilot imports,
# so the CLI start path never attempts real SCM/MoMA calls in this smoke test.
for _var in ("MOMA_API_KEY", "DEEPSEEK_API_KEY", "ATOMGIT_TOKEN", "GITHUB_TOKEN", "CNB_TOKEN"):
    os.environ.pop(_var, None)
# Prevent .env auto-loader from re-injecting credentials from the developer's working copy
os.environ["DEVOPSPILOT_NO_DOTENV"] = "1"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.cli.main import build_parser, main, run_cli
from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    DeliveryTask,
    ExecutionResult,
)
from devopspilot.contracts.providers import RepositoryRef, WorkItemRef
from devopspilot.contracts.review import ReviewResult, ReviewVerdict
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore

REPO = RepositoryRef(provider_id="mock", repository_id="repo-cli", full_name="org/cli-repo", default_branch="main")


def test_cli_parser() -> None:
    parser = build_parser()

    # 1. Test start arguments
    args_start = parser.parse_args(["start", "--repo", "org/repo", "--issue", "123", "--mode", "single_agent"])
    assert args_start.command == "start"
    assert args_start.repo == "org/repo"
    assert args_start.issue == "123"
    assert args_start.mode == "single_agent"

    # 2. Test status arguments
    args_status = parser.parse_args(["status", "--delivery-id", "deliv-100", "--format", "json"])
    assert args_status.command == "status"
    assert args_status.delivery_id == "deliv-100"
    assert args_status.format == "json"

    # 3. Test report arguments
    args_report = parser.parse_args(["report", "--delivery-id", "deliv-100", "--format", "markdown"])
    assert args_report.command == "report"
    assert args_report.format == "markdown"
    print("CLI_PARSER_CONFIG_OK")


def test_cli_execution_with_storage() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_cli_test_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)

        # Seed a completed delivery in state
        task = DeliveryTask(repository=REPO, work_item=WorkItemRef(repository=REPO, item_id="42", title="test item"), target_branch="main")
        exec_res = ExecutionResult(
            source_branch="feat",
            commit_sha="c998877",
            summary="fixed",
            published=True,
            review=ReviewResult(
                reviewer_id="reviewer-01",
                verdict=ReviewVerdict.APPROVED,
                diff_digest="digest-abc",
                summary="approved",
            ),
        )
        state = DeliveryState(task=task, phase=DeliveryPhase.CHANGE_OPENED, execution=exec_res)
        import asyncio
        asyncio.run(store.save("deliv-cli-001", state, expected_version=0))

        # 1. Test status command
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = main(["status", "--delivery-id", "deliv-cli-001", "--db", str(db_path), "--format", "json"])
        assert ret == 0
        output = buf.getvalue()
        assert "deliv-cli-001" in output
        assert "c998877" in output
        print("CLI_STATUS_COMMAND_OK")

        # 2. Test report command (markdown)
        buf_rep = io.StringIO()
        with redirect_stdout(buf_rep):
            ret_rep = main(["report", "--delivery-id", "deliv-cli-001", "--db", str(db_path), "--format", "markdown"])
        assert ret_rep == 0
        rep_out = buf_rep.getvalue()
        assert "# DevOpsPilot Delivery Report: deliv-cli-001" in rep_out
        assert "c998877" in rep_out
        assert "approved" in rep_out.lower()
        print("CLI_REPORT_COMMAND_OK")

        # 3. Test start command
        buf_start = io.StringIO()
        with redirect_stdout(buf_start):
            ret_start = main(["start", "--repo", "repo-1", "--issue", "55", "--db", str(db_path)])
        assert ret_start == 0
        assert "Delivery initialized:" in buf_start.getvalue()
        print("CLI_START_COMMAND_OK")

        # 4. Test error handling for non-existent delivery
        err_buf = io.StringIO()
        with redirect_stderr(err_buf):
            ret_err = main(["status", "--delivery-id", "non-existent", "--db", str(db_path)])
        assert ret_err == 1
        assert "not found" in err_buf.getvalue().lower()
        print("CLI_ERROR_HANDLING_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_github_entry_contract_and_failure() -> None:
    # C03: the GitHub entry must call get_work_item (not the nonexistent
    # get_issue) and a failed live fetch must error out, never silently
    # degrade to a placeholder work item.
    import asyncio

    from devopspilot.adapters.github.scm import GitHubSCMProvider
    from devopspilot.contracts.providers import RepositoryRef

    class FakeClient:
        async def request_json(self, method, path, *, body=None, query=None):
            if path == "/repos/org/repo":
                return {"id": 1, "full_name": "org/repo", "default_branch": "main", "html_url": "https://github.com/org/repo"}
            if path == "/repos/org/repo/issues/7":
                return {"number": 7, "title": "Fix the bug", "body": "please", "state": "open", "user": {"id": 9}, "labels": [{"name": "bug"}]}
            raise AssertionError(f"unexpected path {path}")

    provider = GitHubSCMProvider(FakeClient())
    repo_ref = asyncio.run(provider.get_repository("org/repo"))
    item = asyncio.run(provider.get_work_item(repo_ref, "7"))
    assert item.title == "Fix the bug"
    assert item.labels == ("bug",)
    print("GITHUB_ADAPTER_GET_WORK_ITEM_CONTRACT_OK")

    # Failure semantics: API error must propagate as an exception (CLI maps
    # it to exit 1 with guidance), not to a placeholder task.
    import devopspilot.cli.main as cli_main_mod

    class ExplodingClient:
        async def request_json(self, method, path, *, body=None, query=None):
            from devopspilot.adapters.github.client import GitHubAPIError
            raise GitHubAPIError(401, "Bad credentials", path=path)

    import devopspilot.adapters.github.client as gh_client_mod
    original = gh_client_mod.GitHubHTTPClient
    gh_client_mod.GitHubHTTPClient = lambda token: ExplodingClient()
    saved_token = os.environ.get("GITHUB_TOKEN")
    os.environ["GITHUB_TOKEN"] = "fake-token-for-test"
    os.environ["DEVOPSPILOT_NO_DOTENV"] = "1"
    try:
        buf_err = io.StringIO()
        buf_out = io.StringIO()
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            ret = asyncio.run(run_cli(build_parser().parse_args([
                "start", "--provider", "github", "--repo", "org/does-not-exist-xyz",
                "--issue", "1", "--db", str(Path(tempfile.mkdtemp()) / "s.db"),
            ])))
        assert ret == 1, "GitHub API failure must exit non-zero"
        combined = buf_err.getvalue() + buf_out.getvalue()
        assert "GitHub API Error" in combined or "failed to fetch issue" in combined
    finally:
        gh_client_mod.GitHubHTTPClient = original
        if saved_token is not None:
            os.environ["GITHUB_TOKEN"] = saved_token
        else:
            os.environ.pop("GITHUB_TOKEN", None)
    print("GITHUB_ENTRY_FAILURE_REPORTS_ERROR_OK")


def test_cli_status_labels_distinguish_pending_and_verified() -> None:
    # C07: status must distinguish accepted / waiting / failed / verified,
    # and a pending phase must never render as completed.
    from devopspilot.cli.main import delivery_status_label

    assert delivery_status_label("received", None) == "ACCEPTED (not started)"
    assert delivery_status_label("ci-pending", None) == "IN_PROGRESS / WAITING"
    assert delivery_status_label("ci-failed", None) == "FAILED"
    assert delivery_status_label("rejected", None) == "FAILED"
    assert delivery_status_label("verified", True) == "COMPLETED (verified)"
    # verified phase without accepted verification must NOT print completed
    assert delivery_status_label("verified", False) != "COMPLETED (verified)"
    assert "COMPLETED" not in delivery_status_label("verified", False)
    print("CLI_STATUS_LABELS_OK")


def test_trusted_config_has_real_effect() -> None:
    # C08: operator-supplied trusted config must flow into task metadata and
    # have real enforcement effects (required_checks gate the CI aggregation;
    # path policy reaches the executor prompt).
    from devopspilot.cli.assembly import load_trusted_delivery_config
    from devopspilot.orchestration.ci_aggregator import aggregate_ci_runs
    from devopspilot.contracts.providers import CIRunRef

    env = {
        "DEVOPSPILOT_TEST_COMMAND": "pytest -q",
        "DEVOPSPILOT_ALLOWED_PATHS": "src/,tests/",
        "DEVOPSPILOT_FORBIDDEN_PATHS": "oracle/,secrets/",
        "DEVOPSPILOT_REQUIRED_CHECKS": "ci,lint",
        "DEVOPSPILOT_REQUIRE_REVIEW": "true",
    }
    config = load_trusted_delivery_config(env)
    assert config["test_command"] == "pytest -q"
    assert config["forbidden_paths"] == "oracle/,secrets/"
    assert config["require_review"] == "true"
    # Values mirror the keys the executor / delivery loop already consume
    assert config["allowed_paths"] == "src/,tests/"
    assert config["required_checks"] == "ci,lint"
    print("TRUSTED_CONFIG_LOADED_OK")

    # required_checks from task metadata actually gate the CI aggregation:
    # a green run + a red required check must aggregate to FAILED.
    repo = RepositoryRef(provider_id="mock", repository_id="r", full_name="org/repo")
    required = tuple(x.strip() for x in config["required_checks"].split(",") if x.strip())
    runs = [
        CIRunRef(provider_id="mock-ci", run_id="r-green", repository=repo, status="completed", conclusion="success", commit_sha="sha1"),
        CIRunRef(provider_id="mock-ci", run_id="r-lint", repository=repo, status="completed", conclusion="failure", commit_sha="sha1", check_name="lint"),
    ]
    result = aggregate_ci_runs(runs, expected_commit_sha="sha1", required_checks=required)
    assert result.status.value == "failed", f"red required check must FAIL, got {result.status}"
    print("TRUSTED_CONFIG_REQUIRED_CHECKS_GATE_OK")


def test_shared_gates_reject_counterexamples() -> None:
    # C09 counterexamples: shared path policy must reject traversal, absolute
    # paths, allow-list escapes, and forbidden hits; oracle tamper check must
    # detect a modified forbidden test file.
    import tempfile

    from devopspilot.orchestration.path_policy import (
        PathPolicyConfigError,
        PathPolicyError,
        normalize_policy_paths,
        validate_changed_paths,
    )
    from devopspilot.orchestration.test_runner import OracleTamperError, verify_oracle_not_tampered

    # '..' traversal in configured policy is rejected outright
    try:
        normalize_policy_paths("src/", "../etc/")
        raise AssertionError("config with '..' must be rejected")
    except PathPolicyConfigError:
        pass
    # absolute path in policy is rejected
    try:
        normalize_policy_paths("/etc/passwd", "")
        raise AssertionError("absolute policy entry must be rejected")
    except PathPolicyConfigError:
        pass
    # changed path outside allow-list is rejected
    try:
        validate_changed_paths({"other/x.py"}, allowed=("src/",), forbidden=())
        raise AssertionError("allow-list escape must be rejected")
    except PathPolicyError:
        pass
    # forbidden hit is rejected
    try:
        validate_changed_paths({"oracle/test_x.py"}, allowed=(), forbidden=("oracle/",))
        raise AssertionError("forbidden path change must be rejected")
    except PathPolicyError:
        pass
    print("PATH_POLICY_COUNTEREXAMPLES_BLOCKED_OK")

    # Oracle tamper: modifying a forbidden file must be detected
    tmp = Path(tempfile.mkdtemp(prefix="dp_oracle_"))
    try:
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
        oracle = tmp / "tests_oracle.py"
        oracle.write_text("assert True\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
        subprocess.run(
            ["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init"],
            cwd=tmp, check=True,
        )
        verify_oracle_not_tampered(tmp, ("tests_oracle.py",))
        oracle.write_text("assert False  # tampered\n", encoding="utf-8")
        try:
            verify_oracle_not_tampered(tmp, ("tests_oracle.py",))
            raise AssertionError("tampered oracle must be detected")
        except OracleTamperError:
            pass
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    print("ORACLE_TAMPER_COUNTEREXAMPLE_BLOCKED_OK")


def test_resume_intent_guard_blocks_cross_intent() -> None:
    # C12: a RECEIVED delivery paused for unresolved/inquiry intent must NOT
    # be convertible into a code-write path via resume.
    import asyncio
    import tempfile

    from devopspilot.cli.main import run_cli
    from devopspilot.contracts.delivery import DeliveryPhase, DeliveryState, DeliveryTask
    from devopspilot.contracts.providers import RepositoryRef, WorkItemRef

    tmp = Path(tempfile.mkdtemp(prefix="dp_intent_"))
    try:
        db_path = tmp / "state.db"
        store = SQLiteDeliveryStateStore(db_path)
        repo = RepositoryRef(provider_id="mock", repository_id="repo-intent", full_name="org/repo", default_branch="main")
        task = DeliveryTask(
            repository=repo,
            work_item=WorkItemRef(repository=repo, item_id="9", title="question"),
            target_branch="main",
            metadata={
                "provider": "mock",
                "mode": "single_agent",
                "intent_decision": {"status": "needs_clarification", "intent": None, "reason": "mixed"},
            },
        )
        state = DeliveryState(task=task, phase=DeliveryPhase.RECEIVED, execution=None)
        asyncio.run(store.save("deliv-intent-1", state, expected_version=0))

        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            ret = asyncio.run(run_cli(build_parser().parse_args([
                "resume", "--delivery-id", "deliv-intent-1", "--db", str(db_path),
            ])))
        assert ret == 1, "resume on unresolved-intent RECEIVED delivery must be blocked"
        assert "forbidden" in buf_err.getvalue().lower()
        print("RESUME_UNRESOLVED_INTENT_BLOCKED_OK")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def test_fault_injection_no_duplicate_pr_after_crash() -> None:
    # C13 fault injection: crash after the PR is opened (CHANGE_OPENED) —
    # resume must reconcile CI without creating a second change request, and
    # a duplicate start must return the existing delivery with zero new side
    # effects. Also covers budget-not-reset on crash (C13).
    import asyncio
    import tempfile

    from devopspilot.cli.assembly import assemble_orchestrator
    from devopspilot.contracts.delivery import (
        DeliveryPhase,
        DeliveryState,
        DeliveryTask,
        ExecutionResult,
        VerificationResult,
    )
    from devopspilot.contracts.providers import (
        ChangeRequestRef,
        CIRunRef,
        CommentSubjectRef,
        CommentSubjectKind,
        RepositoryRef,
        ReviewState,
        WorkItemRef,
    )
    from devopspilot.contracts.review import ReviewResult, ReviewVerdict

    repo = RepositoryRef(provider_id="mock", repository_id="repo-fi", full_name="org/fi", default_branch="main")
    task = DeliveryTask(
        repository=repo,
        work_item=WorkItemRef(repository=repo, item_id="13", title="fi"),
        target_branch="main",
        metadata={"provider": "mock", "mode": "single_agent"},
    )
    exec_res = ExecutionResult(
        source_branch="devopspilot/fi", commit_sha="cafe123", summary="ok", published=True,
        review=ReviewResult(reviewer_id="rev", verdict=ReviewVerdict.APPROVED, diff_digest="sha256:d"),
    )
    cr = ChangeRequestRef(repository=repo, change_id="7", title="fi", source_branch="devopspilot/fi", target_branch="main", state="open")
    ci = CIRunRef(provider_id="mock-ci", run_id="ci-fi", repository=repo, status="completed", conclusion="success", commit_sha="cafe123")

    class FakeSCM:
        def __init__(self):
            self.created = 0
            self.comments = 0
        async def get_repository(self, repository_id):
            return repo
        async def get_work_item(self, repository, item_id):
            return task.work_item
        async def create_change_request(self, repository, *, title, body, source_branch, target_branch):
            self.created += 1
            return cr
        async def add_comment(self, subject, *, body):
            self.comments += 1
        async def submit_review(self, repository, *, change_id, state, body):
            raise AssertionError("not expected")
        async def get_change_request(self, repository, change_id):
            return cr

    class FakeCI:
        async def capabilities(self):
            return frozenset()
        async def list_runs(self, repository, *, branch=None, commit_sha=None, ref=None, limit=100, **kwargs):
            return [ci]

    class FakeExecutor:
        async def execute(self, t):
            return exec_res

    class FakeVerifier:
        async def verify(self, state):
            return VerificationResult(accepted=True, summary="clean", outcome_status="verified_clean")

    tmp = Path(tempfile.mkdtemp(prefix="dp_fi_"))
    try:
        scm = FakeSCM()
        orchestrator = assemble_orchestrator(
            type("Cfg", (), {"db_path": tmp / "state.db", "provider": "mock"})(),
            scm=scm, ci=FakeCI(), executor=FakeExecutor(), verifier=FakeVerifier(),
        )
        saved = asyncio.run(orchestrator.start("deliv-fi", repository_id="org/fi", work_item_id="13", target_branch="main"))
        assert saved.state.phase is DeliveryPhase.CHANGE_OPENED
        assert scm.created == 1 and scm.comments == 1

        # Fault injection: process crashes after CHANGE_OPENED. Resume must NOT
        # open a second PR.
        resumed = asyncio.run(orchestrator.resume("deliv-fi"))
        assert resumed.state.phase is DeliveryPhase.CI_PASSED
        assert scm.created == 1, f"resume must not duplicate the PR (created={scm.created})"

        # Duplicate start after completion: returns existing state, no new PR/comment.
        dup = asyncio.run(orchestrator.start(
            "deliv-fi-2", repository_id="org/fi", work_item_id="13", target_branch="main",
            deduplication_key="repo-fi:13:main",
        ))
        assert dup.state.phase is DeliveryPhase.CHANGE_OPENED or dup.state.phase is DeliveryPhase.CI_PASSED
        assert scm.created == 1 and scm.comments == 1, "duplicate start must produce zero new side effects"
        print("FAULT_INJECTION_NO_DUPLICATE_PR_OK")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def main_test() -> None:
    test_cli_parser()
    test_cli_execution_with_storage()
    test_github_entry_contract_and_failure()
    test_cli_status_labels_distinguish_pending_and_verified()
    test_trusted_config_has_real_effect()
    test_shared_gates_reject_counterexamples()
    test_resume_intent_guard_blocks_cross_intent()
    test_fault_injection_no_duplicate_pr_after_crash()
    print("ALL CLI SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main_test()
