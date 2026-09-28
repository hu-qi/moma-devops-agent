"""DevOpsPilot Unified CLI: start, status, resume, and report."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Mapping

from devopspilot.contracts.delivery import DeliveryPhase
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore


def load_dotenv_if_present(path: Path | None = None) -> None:
    """Zero-dependency loader for .env configuration files."""
    # Offline/test guard (C01): skip loading entirely when explicitly disabled,
    # so smoke tests never inherit live credentials from a developer's .env.
    if os.environ.get("DEVOPSPILOT_NO_DOTENV", "").strip() == "1":
        return
    candidates = []
    if path:
        candidates.append(path)
    else:
        # Check current working directory, then parent directories up to git root
        cur = Path.cwd()
        candidates.extend([cur / ".env", cur.parent / ".env"])
        # Also check relative to this source file's project root
        project_root = Path(__file__).resolve().parents[3]
        candidates.append(project_root / ".env")

    for candidate in candidates:
        if candidate.is_file():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    if key and key not in os.environ:
                        os.environ[key] = val
                break
            except Exception:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="devopspilot",
        description="DevOpsPilot: Autonomous AI DevOps Delivery Agent",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. start
    start_p = subparsers.add_parser("start", help="Start a new delivery task")
    start_p.add_argument("--provider", choices=["github", "atomgit", "cnb", "mock"], help="Target code hosting provider")
    start_p.add_argument("--repo", required=True, help="Repository ID, full name, or URL")
    start_p.add_argument("--issue", required=True, help="Work item / issue ID")
    start_p.add_argument("--delivery-id", help="Explicit delivery ID (defaults to uuid)")
    start_p.add_argument("--target", help="Target branch name")
    start_p.add_argument(
        "--mode",
        choices=["single_agent", "agent_team"],
        default="single_agent",
        help="Execution mode (default: single_agent)",
    )
    start_p.add_argument(
        "--intent",
        choices=["inquiry", "code_change"],
        help="Explicit intent override (inquiry = direct issue comment Q&A, code_change = branch + PR)",
    )
    start_p.add_argument("--db", default=".devopspilot/state.db", help="Path to state database")

    # 2. status
    status_p = subparsers.add_parser("status", help="Query status of an existing delivery")
    status_p.add_argument("--delivery-id", required=True, help="Delivery ID to query")
    status_p.add_argument("--db", default=".devopspilot/state.db", help="Path to state database")
    status_p.add_argument("--format", choices=["json", "text"], default="text", help="Output format")

    # 3. resume
    resume_p = subparsers.add_parser("resume", help="Resume delivery from last checkpoint")
    resume_p.add_argument("--delivery-id", required=True, help="Delivery ID to resume")
    resume_p.add_argument("--db", default=".devopspilot/state.db", help="Path to state database")

    # 4. report
    report_p = subparsers.add_parser("report", help="Generate delivery report")
    report_p.add_argument("--delivery-id", required=True, help="Delivery ID to report")
    report_p.add_argument("--db", default=".devopspilot/state.db", help="Path to state database")
    report_p.add_argument("--format", choices=["json", "markdown", "text"], default="markdown")

    # 5. demo
    demo_p = subparsers.add_parser("demo", help="Demonstrate delivery pathways (deterministic, recorded, live)")
    demo_p.add_argument(
        "--mode",
        choices=["deterministic", "recorded", "live"],
        default="deterministic",
        help="Demonstration mode (default: deterministic)",
    )

    return parser


def resolve_provider_and_repo(provider_arg: str | None, repo_arg: str) -> tuple[str, str]:
    """Resolve provider ID and clean repository path/name from CLI arguments."""
    repo = repo_arg.strip()
    if repo.startswith("https://") or repo.startswith("http://"):
        from urllib.parse import urlparse
        parsed = urlparse(repo)
        path = parsed.path.strip("/").removesuffix(".git")
        if "atomgit.com" in parsed.netloc:
            return provider_arg or "atomgit", path
        if "github.com" in parsed.netloc:
            return provider_arg or "github", path
        if "cnb.cool" in parsed.netloc:
            return provider_arg or "cnb", path
        return provider_arg or "mock", path

    if provider_arg:
        return provider_arg, repo

    # Infer from local git remote if available
    try:
        import subprocess
        res = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        url = res.stdout.strip()
        if "atomgit.com" in url:
            return "atomgit", repo
        if "cnb.cool" in url:
            return "cnb", repo
    except Exception:
        pass

    return "github", repo


def format_state_text(delivery_id: str, version: int, state: Any) -> str:
    lines = [
        f"Delivery ID:   {delivery_id}",
        f"State Version: {version}",
        f"Phase:         {state.phase.value}",
    ]
    if state.phase.value == "answered":
        lines.append("Type:          Inquiry / Direct Q&A (No PR required)")
        if state.verification:
            lines.append(f"Verified:      {state.verification.accepted} ({state.verification.summary})")
        return "\n".join(lines)

    commit = state.execution.commit_sha if state.execution else "none"
    pr = state.change_request.change_id if state.change_request else "none"
    ci = state.ci_run.status if state.ci_run else "none"
    lines.extend([
        f"Commit:        {commit}",
        f"Change PR:     {pr}",
        f"CI Status:     {ci}",
    ])
    if state.verification:
        lines.append(f"Verified:      {state.verification.accepted} ({state.verification.summary})")
    return "\n".join(lines)


def format_state_markdown(delivery_id: str, version: int, state: Any) -> str:
    from devopspilot.contracts.branding import BrandConfig
    brand = BrandConfig.from_env()
    commit = state.execution.commit_sha if state.execution else "N/A"
    pr = state.change_request.change_id if state.change_request else "N/A"
    review = state.execution.review.verdict.value if (state.execution and state.execution.review) else "none"
    return f"""# {brand.devopspilot_name} Delivery Report: {delivery_id}

- **Version**: {version}
- **Phase**: `{state.phase.value}`
- **Repository**: `{state.task.repository.full_name}`
- **Issue**: `{state.task.work_item.item_id}` — {state.task.work_item.title}
- **Target Branch**: `{state.task.target_branch}`
- **Commit SHA**: `{commit}`
- **Change Request**: `{pr}`
- **Review Verdict**: `{review}`
- **Verification Status**: `{'ACCEPTED' if state.verification and state.verification.accepted else 'PENDING'}`

---
*Powered by {brand.devopspilot_markdown} on China Mobile Cloud ({brand.moma_markdown}) platform.*
"""


async def run_cli(args: argparse.Namespace) -> int:
    if args.command == "demo":
        # C09: demo modes must reflect real, verifiable evidence —
        # deterministic runs the local integration fixture suite,
        # recorded reads saved evidence, live delegates to the real entry point.
        if args.mode == "deterministic":
            suite = Path(__file__).resolve().parents[3] / "experiments" / "end-to-end-integration-suite" / "main.py"
            if not suite.is_file():
                print(f"Deterministic demo requires local fixture suite not found: {suite}")
                return 1
            print("=== DevOpsPilot Demo: Deterministic (local integration fixture suite) ===")
            import subprocess
            proc = subprocess.run([sys.executable, str(suite)])
            if proc.returncode != 0:
                print(f"Deterministic demo FAILED (exit {proc.returncode}). Fix failures before presenting demos.")
                return proc.returncode
            print("Deterministic demo passed: local fixture suite completed successfully.")
            return 0

        if args.mode == "recorded":
            evidence_dir = Path(__file__).resolve().parents[3] / "docs" / "evidence"
            files = sorted(p.name for p in evidence_dir.glob("*")) if evidence_dir.is_dir() else []
            if not files:
                print("Recorded demo has no saved evidence files; nothing to present honestly.")
                return 1
            print("=== DevOpsPilot Demo: Recorded Evidence (saved artifacts) ===")
            for name in files:
                print(f"- {name}")
            print("These are the only recorded artifacts available; no fabricated run summaries.")
            return 0

        if args.mode == "live":
            gh_token = os.environ.get("GITHUB_TOKEN")
            moma_key = os.environ.get("MOMA_API_KEY")
            if not gh_token or not moma_key:
                print("Notice: Live mode requires GITHUB_TOKEN and MOMA_API_KEY environment variables.")
                print("To run deterministic demo without credentials, use: devopspilot demo --mode deterministic")
                return 1
            print("Starting live E2E delivery via the real CLI entry point...")
            live_target = os.environ.get("GITHUB_REPOSITORY", "")
            live_issue = os.environ.get("DEVOPSPILOT_E2E_ISSUE", "")
            if not live_target or not live_issue:
                print("Live demo requires GITHUB_REPOSITORY and DEVOPSPILOT_E2E_ISSUE environment variables.")
                return 1
            # Build args through the real parser so every required attribute exists
            live_args = build_parser().parse_args([
                "start", "--repo", live_target, "--issue", live_issue,
                "--mode", "single_agent", "--target-branch", "main",
                "--db", ".devopspilot/state.db",
            ])
            return await run_cli(live_args)

    db_path = Path(getattr(args, "db", ".devopspilot/state.db"))
    if not db_path.exists() and args.command in {"status", "resume", "report"}:
        sys.stderr.write(f"Error: State database '{args.db}' not found.\n")
        return 1

    store = SQLiteDeliveryStateStore(db_path)

    if args.command == "status":
        stored = await store.load(args.delivery_id)
        if stored is None:
            sys.stderr.write(f"Error: Delivery '{args.delivery_id}' not found in {args.db}\n")
            return 1
        if args.format == "json":
            out = {
                "delivery_id": stored.delivery_id,
                "version": stored.version,
                "phase": stored.state.phase.value,
                "commit_sha": stored.state.execution.commit_sha if stored.state.execution else None,
                "pr_id": stored.state.change_request.change_id if stored.state.change_request else None,
            }
            print(json.dumps(out, indent=2))
        else:
            print(format_state_text(stored.delivery_id, stored.version, stored.state))
        return 0

    if args.command == "report":
        stored = await store.load(args.delivery_id)
        if stored is None:
            sys.stderr.write(f"Error: Delivery '{args.delivery_id}' not found in {args.db}\n")
            return 1

        from devopspilot.orchestration.report_service import DeliveryReportService
        from devopspilot.persistence.remediation_ledger import SQLiteRemediationLedger

        remediation_db = db_path.parent / "remediation.db"
        remediation_records = None
        if remediation_db.exists():
            ledger = SQLiteRemediationLedger(remediation_db)
            remediation_records = await ledger.list(args.delivery_id)

        report = DeliveryReportService.generate_report(stored, remediation_records)

        if args.format == "json":
            print(report.to_json())
        elif args.format == "markdown":
            print(report.to_markdown())
        else:
            print(format_state_text(stored.delivery_id, stored.version, stored.state))
        return 0

    if args.command == "resume":
        stored = await store.load(args.delivery_id)
        if stored is None:
            sys.stderr.write(f"Error: Delivery '{args.delivery_id}' not found in {args.db}\n")
            return 1

        provider = stored.state.task.metadata.get("provider", "mock")
        repo = stored.state.task.repository.full_name
        target_br = stored.state.task.target_branch
        mode = stored.state.task.metadata.get("mode", "single_agent")

        from devopspilot.cli.assembly import AppConfig, assemble_live_orchestrator, setup_model_environment
        has_model = setup_model_environment()

        if provider in {"atomgit", "github"} and has_model:
            config = AppConfig(
                db_path=db_path,
                provider=provider,
                default_target_branch=target_br,
                execution_mode=mode,
            )
            try:
                orchestrator = assemble_live_orchestrator(config, repo, store=store)
                resumed = await orchestrator.resume(args.delivery_id)
                print(f"Delivery {args.delivery_id} resumed: phase={resumed.state.phase.value}")
                return 0
            except Exception as exc:
                sys.stderr.write(f"Error resuming delivery {args.delivery_id}: {exc}\n")
                return 1

        print(f"Delivery {args.delivery_id} resumed from phase={stored.state.phase.value}")
        return 0

    if args.command == "start":
        deliv_id = args.delivery_id or f"deliv-{uuid.uuid4().hex[:8]}"
        provider, repo = resolve_provider_and_repo(getattr(args, "provider", None), args.repo)
        target_br = getattr(args, "target", None) or "main"
        print(f"Delivery initialized: id={deliv_id} provider={provider} repo={repo} issue={args.issue} mode={args.mode}")

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
            RepositoryRef,
            WorkItemRef,
        )
        from devopspilot.contracts.review import ReviewResult, ReviewVerdict

        # Step 1: Real Work Item & Repo resolution
        repo_ref = RepositoryRef(
            provider_id=provider,
            repository_id=f"repo-{repo.replace('/', '-')}",
            full_name=repo,
            default_branch=target_br,
            web_url=f"https://{provider}.com/{repo}" if provider in {"atomgit", "github"} else f"https://local/{repo}",
        )
        work_item = WorkItemRef(
            repository=repo_ref,
            item_id=str(args.issue),
            title=f"Task #{args.issue}: Feature & CI Delivery",
            body=f"Tracked issue #{args.issue} on {provider}",
        )

        real_issue_fetched = False
        scm_client = None
        if provider == "atomgit":
            token = os.environ.get("ATOMGIT_TOKEN")
            if token:
                try:
                    from devopspilot.adapters.atomgit.client import AtomGitHTTPClient
                    from devopspilot.adapters.atomgit.scm import AtomGitSCMProvider
                    client = AtomGitHTTPClient(token=token)
                    scm_client = AtomGitSCMProvider(client)
                    live_repo = await scm_client.get_repository(repo)
                    live_item = await scm_client.get_issue(live_repo, str(args.issue))
                    repo_ref = live_repo
                    work_item = live_item
                    real_issue_fetched = True
                    print(f"[1/5] Real AtomGit API: Issue #{args.issue} resolved -> '{live_item.title}' (State: {live_item.state})")
                except Exception as exc:
                    print(f"[1/5] AtomGit API Warning: Could not fetch Issue #{args.issue} live ({exc}). Using offline reference.")
            else:
                print(f"[1/5] AtomGit API: No ATOMGIT_TOKEN provided. Operating in offline/mock reference mode.")
        elif provider == "github":
            token = os.environ.get("GITHUB_TOKEN")
            if token:
                try:
                    from devopspilot.adapters.github.scm import GitHubSCMProvider
                    scm_client = GitHubSCMProvider(token=token)
                    live_repo = await scm_client.get_repository(repo)
                    live_item = await scm_client.get_issue(live_repo, str(args.issue))
                    repo_ref = live_repo
                    work_item = live_item
                    real_issue_fetched = True
                    print(f"[1/5] Real GitHub API: Issue #{args.issue} resolved -> '{live_item.title}'")
                except Exception as exc:
                    print(f"[1/5] GitHub API Warning: {exc}. Using offline reference.")
            else:
                print(f"[1/5] GitHub API: No GITHUB_TOKEN provided. Operating in offline reference mode.")
        else:
            print(f"[1/5] Work item resolved: #{args.issue} - '{work_item.title}'")

        # Step 2: Planning & Intent Classification (structured decision, policy v2)
        from devopspilot.routing.intent import (
            DecisionStatus,
            TaskIntent,
            TaskIntentClassifier,
        )
        intent_classifier = TaskIntentClassifier()
        intent_metadata = {}
        if getattr(args, "intent", None):
            intent_metadata["intent"] = args.intent
        intent_decision = await intent_classifier.classify_async(
            title=work_item.title,
            body=work_item.body,
            labels=getattr(work_item, "labels", ()),
            metadata=intent_metadata,
        )

        from devopspilot.cli.assembly import AppConfig, assemble_live_orchestrator, setup_model_environment
        has_model = setup_model_environment()

        if intent_decision.status is DecisionStatus.NEEDS_CLARIFICATION:
            # Unresolved intent: NEVER default to code change / writing.
            # Persist a paused state for human clarification instead.
            print(f"[2/5] Task Planning: Intent UNRESOLVED ({intent_decision.reason_code.value}: {intent_decision.reason})")
            print("[3/5] Execution: PAUSED - Ambiguous intent requires human clarification (no write actions taken).")

            final_state = DeliveryState(
                task=DeliveryTask(
                    repository=repo_ref,
                    work_item=work_item,
                    target_branch=target_br,
                    metadata={
                        "delivery_id": deliv_id,
                        "mode": args.mode,
                        "provider": provider,
                        "intent_decision": intent_decision.as_dict(),
                    },
                ),
                phase=DeliveryPhase.RECEIVED,
                execution=None,
                change_request=None,
                ci_run=None,
                verification=VerificationResult(
                    accepted=False,
                    summary=(
                        f"Intent unresolved ({intent_decision.reason_code.value}); "
                        "paused for clarification. No branch, PR or comment was created."
                    ),
                    outcome_status="evidence_incomplete",
                ),
            )
            await store.save(deliv_id, final_state, expected_version=0)
            print(f"\nDelivery status: id={deliv_id} phase=RECEIVED (Paused: intent needs clarification)")
            print("To resume: set explicit intent via metadata (e.g. issue label 'inquiry' or 'code_change') and run:")
            print(f"  devopspilot resume --delivery-id {deliv_id}")
            print(f"To inspect state: devopspilot status --delivery-id {deliv_id}")
            return 0

        task_intent = intent_decision.intent
        intent_persist = intent_decision.as_dict()
        if task_intent is TaskIntent.INQUIRY:
            print(f"[2/5] Task Planning: Classified as 'inquiry' ({intent_decision.reason_code.value}) - Direct Q&A mode, no PR required")
        else:
            print(f"[2/5] Execution planning: mode={args.mode} (Single Agent First)")

        if provider in {"atomgit", "github"}:
            if not has_model:
                print("      Model Engine Notice: No MOMA_API_KEY detected in environment / .env.")
                print("[3/5] Coding: PAUSED - No MoMA AI model credentials available to inspect codebase and write code.")
                print(f"[4/5] Pull/Merge Request: SKIPPED - No code changes produced; no branch pushed to {provider}.")
                print("[5/5] CI Verification: INCOMPLETE - Awaiting implementation.")

                final_state = DeliveryState(
                    task=DeliveryTask(
                        repository=repo_ref,
                        work_item=work_item,
                        target_branch=target_br,
                        metadata={
                            "delivery_id": deliv_id,
                            "mode": args.mode,
                            "provider": provider,
                            "intent_decision": intent_persist,
                        },
                    ),
                    phase=DeliveryPhase.RECEIVED,
                    execution=None,
                    change_request=None,
                    ci_run=None,
                    verification=VerificationResult(
                        accepted=False,
                        summary="Delivery registered live on SCM, but paused awaiting MOMA_API_KEY.",
                        outcome_status="evidence_incomplete",
                    ),
                )
                await store.save(deliv_id, final_state, expected_version=0)
                print(f"\nDelivery status: id={deliv_id} phase=RECEIVED (Paused: awaiting MoMA AI credentials)")
                print(f"To configure: add MOMA_API_KEY to your .env file, then run:")
                print(f"  devopspilot resume --delivery-id {deliv_id}")
                print(f"To inspect state: devopspilot status --delivery-id {deliv_id}")
                return 0

            # 2.1 Branch for Direct Inquiry/Question (No PR required)
            if task_intent is TaskIntent.INQUIRY and scm_client is not None:
                print("[3/5] AI Analysis: Inspecting repository structure and analyzing inquiry via MoMA...")
                repo_dir = Path.home() / ".devopspilot" / "repos" / repo
                if not repo_dir.exists():
                    try:
                        from devopspilot.adapters.git.auth import build_clone_auth_args, sanitize_error
                        token = os.environ.get("ATOMGIT_TOKEN" if provider == "atomgit" else "GITHUB_TOKEN", "").strip()
                        clone_url = f"https://{provider}.com/{repo}.git"
                        import subprocess
                        subprocess.run(
                            ["git", "clone", "--depth", "1", *build_clone_auth_args(provider, token), clone_url, str(repo_dir)],
                            check=True, capture_output=True,
                        )
                    except subprocess.CalledProcessError as clone_err:
                        stderr_text = clone_err.stderr.decode("utf-8", "replace") if clone_err.stderr else str(clone_err)
                        print(f"[3/5] Clone failed: {sanitize_error(stderr_text)[:300]}")
                    except Exception as clone_exc:
                        print(f"[3/5] Clone failed: {sanitize_error(str(clone_exc))[:300]}")

                from devopspilot.orchestration.inquiry_handler import InquiryHandler
                inquiry_task = DeliveryTask(
                    repository=repo_ref,
                    work_item=work_item,
                    target_branch=target_br,
                    metadata={"delivery_id": deliv_id, "mode": "direct_inquiry", "intent": "inquiry", "provider": provider, "intent_decision": intent_persist},
                )
                handler = InquiryHandler(scm=scm_client)
                try:
                    await handler.answer_and_comment(inquiry_task, workspace_path=repo_dir)
                    print(f"[4/5] Issue Response: Direct answer successfully posted as comment to {provider} Issue #{args.issue}!")
                    print(f"[5/5] Delivery Completed: phase=answered (Direct Q&A response complete, PR and CI skipped)")

                    final_state = DeliveryState(
                        task=inquiry_task,
                        phase=DeliveryPhase.ANSWERED,
                        execution=None,
                        change_request=None,
                        ci_run=None,
                        verification=VerificationResult(
                            accepted=True,
                            summary=f"Inquiry answered directly via comment on issue #{args.issue}.",
                            outcome_status="verified_clean",
                        ),
                    )
                    saved_final = await store.save(deliv_id, final_state, expected_version=0)
                    print(f"\nDelivery completed: id={deliv_id} phase={saved_final.state.phase.value}")
                    print(f"To query status:  devopspilot status --delivery-id {deliv_id}")
                    print(f"To export report: devopspilot report --delivery-id {deliv_id} --format markdown")
                    return 0
                except Exception as inq_err:
                    # Inquiry failure must NOT fall through to AI coding (no cross-intent
                    # fallback). Stay within the inquiry path: persist a recoverable
                    # failed state; only inquiry retry/resume is allowed next.
                    print(f"[4/5] Inquiry response failed: {inq_err}")
                    print("[5/5] Execution: FAILED - Staying in inquiry mode; coding/PR path is blocked for this delivery.")

                    failed_state = DeliveryState(
                        task=inquiry_task,
                        phase=DeliveryPhase.RECEIVED,
                        execution=None,
                        change_request=None,
                        ci_run=None,
                        verification=VerificationResult(
                            accepted=False,
                            summary=(
                                f"Inquiry handling failed ({inq_err}); delivery paused for inquiry retry. "
                                "Cross-intent fallback to code change is forbidden."
                            ),
                            outcome_status="evidence_incomplete",
                        ),
                    )
                    await store.save(deliv_id, failed_state, expected_version=0)
                    print(f"\nDelivery status: id={deliv_id} phase=RECEIVED (Paused: inquiry retry needed)")
                    print(f"To retry inquiry: devopspilot resume --delivery-id {deliv_id}")
                    print(f"To inspect state: devopspilot status --delivery-id {deliv_id}")
                    return 1

            # 2.2 Branch for Code Change: Real LLM coding & end-to-end execution path on MoMA platform!
            print(f"[3/5] AI Coding: Invoking OpenJiuwen AgentTeam via MoMA platform ({os.environ.get('MOMA_API_BASE')})...")
            config = AppConfig(
                db_path=db_path,
                provider=provider,
                default_target_branch=target_br,
                execution_mode=args.mode,
            )
            try:
                orchestrator = assemble_live_orchestrator(config, repo, store=store)

                # C07: drive the delivery through the public orchestration service
                # (lease + durable checkpoints), NOT by hand-driving private loop
                # methods with ad-hoc saves.
                saved_opened = await orchestrator.start(
                    deliv_id,
                    repository_id=repo,
                    work_item_id=str(args.issue),
                    target_branch=target_br,
                    task_metadata={
                        "delivery_id": deliv_id,
                        "mode": args.mode,
                        "provider": provider,
                        "source_branch": f"devopspilot/issue-{args.issue}-{deliv_id[-4:]}",
                    },
                )
                opened_state = saved_opened.state

                exec_meta = opened_state.execution.metadata if opened_state.execution else {}
                commit_sha = opened_state.execution.commit_sha if opened_state.execution else "none"
                branch_name = opened_state.execution.source_branch if opened_state.execution else "none"
                review_verdict = (
                    opened_state.execution.review.verdict.value
                    if (opened_state.execution and opened_state.execution.review)
                    else "none"
                )
                print(f"[3/5] AI Coding complete: branch={branch_name} commit={commit_sha}")
                print(f"      Independent Review Verdict: {review_verdict.upper()} (Quality gate)")

                # 3. Open Change Request (PR / MR) — already checkpointed by service
                print(f"[4/5] Change Request: Opening live Pull Request on {provider}...")
                cr_url = opened_state.change_request.web_url if opened_state.change_request else "none"
                print(f"[4/5] Live Change Request opened on {provider}: {cr_url}")

                # 4. CI Reconciliation via public service (crash-window safe: persisted)
                print("[5/5] CI Verification: Checking workflow runs...")
                try:
                    reconciled = await orchestrator.reconcile_ci(deliv_id)
                    final_state = reconciled.state
                except Exception as ci_err:
                    print(f"[5/5] CI Verification Note: {ci_err}")
                    final_state = opened_state

                print(f"\nDelivery completed: id={deliv_id} phase={final_state.phase.value}")
                print(f"To query status:  devopspilot status --delivery-id {deliv_id}")
                print(f"To export report: devopspilot report --delivery-id {deliv_id} --format markdown")
                return 0
            except Exception as exc:
                sys.stderr.write(f"\nExecution error during delivery {deliv_id}: {exc}\n")
                return 1

        else:
            # Explicit Mock / Dry-Run Simulation Mode
            if task_intent is TaskIntent.INQUIRY:
                print(f"[DRY-RUN 3/5] Simulated analysis: Inspecting repository structure and analyzing inquiry")
                print(f"[DRY-RUN 4/5] Simulated comment: Direct answer successfully posted to Issue #{args.issue}")
                print("[DRY-RUN 5/5] Delivery complete: Phase=ANSWERED (Direct Q&A response)")

                final_state = DeliveryState(
                    task=DeliveryTask(
                        repository=repo_ref,
                        work_item=work_item,
                        target_branch=target_br,
                        metadata={"delivery_id": deliv_id, "mode": "simulation", "intent": "inquiry"},
                    ),
                    phase=DeliveryPhase.ANSWERED,
                    execution=None,
                    change_request=None,
                    ci_run=None,
                    verification=VerificationResult(
                        accepted=True,
                        summary="Deterministic simulation: direct inquiry answered via issue comment.",
                        outcome_status="verified_clean",
                    ),
                )
                await store.save(deliv_id, final_state, expected_version=0)
                print(f"\nDelivery completed: id={deliv_id} phase={final_state.phase.value}")
                print(f"To query status:  devopspilot status --delivery-id {deliv_id}")
                print(f"To export report: devopspilot report --delivery-id {deliv_id} --format markdown")
                return 0

            mock_commit = f"c{uuid.uuid4().hex[:7]}"
            branch_name = f"feat/issue-{args.issue}-{deliv_id[-4:]}"
            cr_id = f"mr-{args.issue}" if provider == "atomgit" else f"pr-{args.issue}"
            print(f"[DRY-RUN 3/5] Simulated coding: branch={branch_name} commit={mock_commit}")
            print("              Simulated Review: APPROVED (Deterministic Offline Fallback)")
            print(f"[DRY-RUN 4/5] Simulated change request: mock://{repo}/pulls/{args.issue}")
            print("[DRY-RUN 5/5] Simulated CI: SUCCESS (Deterministic Verification)")

            cr_ref = ChangeRequestRef(
                repository=repo_ref,
                change_id=cr_id,
                title=work_item.title,
                source_branch=branch_name,
                target_branch=target_br,
                state="open",
                web_url=f"https://local/{repo}/pulls/{args.issue}",
            )
            ci_run = CIRunRef(
                provider_id=provider,
                run_id=f"run-{uuid.uuid4().hex[:6]}",
                repository=repo_ref,
                status="success",
                conclusion="success",
                commit_sha=mock_commit,
                web_url=f"https://local/{repo}/actions/runs/1",
            )
            verification = VerificationResult(
                accepted=True,
                summary="Deterministic simulation verification passed cleanly.",
                outcome_status="verified_clean",
            )
            final_state = DeliveryState(
                task=DeliveryTask(
                    repository=repo_ref,
                    work_item=work_item,
                    target_branch=target_br,
                    metadata={"delivery_id": deliv_id, "mode": "simulation"},
                ),
                phase=DeliveryPhase.VERIFIED,
                execution=ExecutionResult(
                    source_branch=branch_name,
                    commit_sha=mock_commit,
                    summary="Deterministic simulation execution (Zero Model API Cost)",
                    published=True,
                    test_summary="Local unit tests: 100% pass",
                    review=ReviewResult(
                        reviewer_id="reviewer-simulation",
                        verdict=ReviewVerdict.APPROVED,
                        diff_digest=f"sha256-{deliv_id[-8:]}",
                        commit_sha=mock_commit,
                        summary="Deterministic Simulation Review: no findings",
                    ),
                ),
                change_request=cr_ref,
                ci_run=ci_run,
                verification=verification,
            )
            await store.save(deliv_id, final_state, expected_version=0)
            print(f"\nDelivery simulation completed: id={deliv_id} phase=VERIFIED (SIMULATED)")
            print(f"To query status:  devopspilot status --delivery-id {deliv_id}")
            print(f"To export report: devopspilot report --delivery-id {deliv_id} --format markdown")
            return 0

    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_present()
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(run_cli(args))


if __name__ == "__main__":
    sys.exit(main())
