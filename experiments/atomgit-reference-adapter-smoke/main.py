"""Credential-free smoke test for the AtomGit reference adapters."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.adapters.atomgit import AtomGitCIProvider, AtomGitSCMProvider
from devopspilot.contracts.providers import (
    CICapability,
    CommentSubjectKind,
    CommentSubjectRef,
    ReviewState,
    SCMCapability,
)


class FakeAtomGitClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method, path, body))

        if method == "GET" and path == "/repos/atom-org/demo":
            return {
                "id": 1001,
                "full_name": "atom-org/demo",
                "default_branch": "main",
                "html_url": "https://atomgit.com/atom-org/demo",
            }
        if method == "GET" and path == "/repos/atom-org/demo/issues":
            return [
                {
                    "number": 1,
                    "title": "Fix login crash",
                    "state": "open",
                    "body": "NPE in auth",
                    "html_url": "https://atomgit.com/atom-org/demo/issues/1",
                }
            ]
        if method == "GET" and path == "/repos/atom-org/demo/issues/1":
            return {
                "number": 1,
                "title": "Fix login crash",
                "state": "open",
                "body": "NPE in auth",
                "html_url": "https://atomgit.com/atom-org/demo/issues/1",
            }
        if method == "POST" and path == "/repos/atom-org/demo/pulls":
            return {
                "number": 10,
                "title": body["title"],
                "state": "open",
                "head": {"ref": body["head"], "sha": "c0ffee"},
                "base": {"ref": body["base"], "sha": "b00b00"},
                "html_url": "https://atomgit.com/atom-org/demo/pulls/10",
            }
        if method == "GET" and path == "/repos/atom-org/demo/pulls/10":
            return {
                "number": 10,
                "title": "Fix login crash PR",
                "state": "open",
                "head": {"ref": "fix/login", "sha": "c0ffee"},
                "base": {"ref": "main", "sha": "b00b00"},
                "html_url": "https://atomgit.com/atom-org/demo/pulls/10",
            }
        if method == "POST" and path == "/repos/atom-org/demo/issues/10/comments":
            return {"id": 888}
        if method == "POST" and path == "/repos/atom-org/demo/pulls/10/reviews":
            return {
                "id": 555,
                "state": "APPROVED",
                "body": body.get("body"),
            }
        if method == "GET" and path == "/repos/atom-org/demo/actions/runs":
            return {
                "workflow_runs": [
                    {
                        "id": 2001,
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://atomgit.com/atom-org/demo/actions/runs/2001",
                    }
                ]
            }
        if method == "GET" and path == "/repos/atom-org/demo/actions/runs/2001":
            return {
                "id": 2001,
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://atomgit.com/atom-org/demo/actions/runs/2001",
            }
        if method == "GET" and path == "/repos/atom-org/demo/actions/runs/2001/jobs":
            return {
                "jobs": [
                    {
                        "id": 3001,
                        "name": "build-and-test",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://atomgit.com/atom-org/demo/actions/runs/2001/jobs/3001",
                    }
                ]
            }
        if method == "POST" and path == "/repos/atom-org/demo/actions/runs/2001/cancel":
            return {}
        if method == "POST" and path == "/repos/atom-org/demo/actions/runs/2001/rerun-failed-jobs":
            return {}
        if method == "POST" and path == "/repos/atom-org/demo/actions/workflows/ci.yml/dispatches":
            return {}

        raise NotImplementedError(f"Unhandled fake request: {method} {path}")

    async def request_bytes(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
    ) -> bytes:
        if method == "GET" and path == "/repos/atom-org/demo/actions/jobs/3001/logs":
            return b"Build passed without errors\n"
        raise NotImplementedError(f"Unhandled fake request_bytes: {method} {path}")


async def test_scm() -> None:
    client = FakeAtomGitClient()
    secret = "atomgit_secret_key"
    scm = AtomGitSCMProvider(client, webhook_secret=secret)

    caps = await scm.capabilities()
    assert SCMCapability.ISSUES in caps
    assert SCMCapability.CHANGE_REQUESTS in caps
    assert SCMCapability.REVIEWS in caps
    print("ATOMGIT_SCM_CAPABILITIES_OK")

    repo = await scm.get_repository("atom-org/demo")
    assert repo.full_name == "atom-org/demo"
    assert repo.provider_id == "atomgit"
    print("ATOMGIT_GET_REPOSITORY_OK")

    issues = await scm.list_issues(repo)
    assert len(issues) == 1
    assert issues[0].item_id == "1"

    issue = await scm.get_issue(repo, "1")
    assert issue.title == "Fix login crash"
    print("ATOMGIT_ISSUES_OK")

    pr = await scm.create_change_request(
        repo,
        title="Fix login crash PR",
        body="Closes #1",
        source_branch="fix/login",
        target_branch="main",
    )
    assert pr.change_id == "10"
    assert pr.source_branch == "fix/login"
    print("ATOMGIT_CREATE_PR_OK")

    pr_fetched = await scm.get_change_request(repo, "10")
    assert pr_fetched.change_id == "10"

    await scm.add_comment(
        CommentSubjectRef(repo, pr.change_id, CommentSubjectKind.CHANGE_REQUEST),
        body="LGTM!",
    )
    print("ATOMGIT_COMMENT_OK")

    review = await scm.submit_review(
        pr,
        state=ReviewState.APPROVE,
        body="Approved by DevOpsPilot Reviewer",
    )
    assert review.state == ReviewState.APPROVE
    print("ATOMGIT_SUBMIT_REVIEW_OK")

    # Webhook signature validation & normalization
    payload_dict = {
        "repository": {"id": 1001, "full_name": "atom-org/demo"},
        "sender": {"id": 999},
        "action": "opened",
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    event = await scm.normalize_webhook(
        headers={
            "x-atomgit-signature": f"sha256={sig}",
            "x-atomgit-event": "issues",
            "x-atomgit-delivery": "evt_atom_123",
        },
        body=raw_body,
    )
    assert event.event_type == "issues"
    assert event.event_id == "evt_atom_123"
    assert event.repository.full_name == "atom-org/demo"
    print("ATOMGIT_WEBHOOK_NORMALIZATION_OK")


async def test_ci() -> None:
    client = FakeAtomGitClient()
    ci = AtomGitCIProvider(client)

    caps = await ci.capabilities()
    assert CICapability.RUNS in caps
    assert CICapability.LOGS in caps
    assert CICapability.TRIGGER in caps
    assert CICapability.CANCEL in caps
    print("ATOMGIT_CI_CAPABILITIES_OK")

    from devopspilot.contracts.providers import RepositoryRef
    repo = RepositoryRef(
        provider_id="atomgit",
        repository_id="1001",
        full_name="atom-org/demo",
    )

    runs = await ci.list_runs(repo)
    assert len(runs) == 1
    assert runs[0].run_id == "2001"
    assert runs[0].conclusion == "success"

    run = await ci.get_run(repo, "2001")
    assert run.run_id == "2001"
    print("ATOMGIT_RUN_DISCOVERY_OK")

    logs = [log async for log in ci.stream_logs(run)]
    assert len(logs) == 1
    assert "Build passed" in logs[0].content
    print("ATOMGIT_STREAM_LOGS_OK")

    await ci.trigger_workflow(repo, "ci.yml", ref="main")
    await ci.cancel_run(repo, "2001")
    await ci.rerun_failed(repo, "2001")
    print("ATOMGIT_CI_OPERATIONS_OK")


async def main() -> None:
    await test_scm()
    await test_ci()
    print("ALL ATOMGIT ADAPTER SMOKE TESTS PASSED.")


if __name__ == "__main__":
    asyncio.run(main())
