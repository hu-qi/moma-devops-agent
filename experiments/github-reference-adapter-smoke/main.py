"""Credential-free behavior smoke for the GitHub reference adapters."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import Any, Mapping

from devopspilot.adapters.github import GitHubCIProvider, GitHubSCMProvider
from devopspilot.contracts.providers import (
    CICapability,
    CommentSubjectKind,
    CommentSubjectRef,
    ReviewState,
    SCMCapability,
)


class FakeGitHubClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Mapping[str, Any] | None]] = []

    async def request_json(
        self, method: str, path: str, *, body: Mapping[str, Any] | None = None,
        query: Mapping[str, Any] | None = None,
    ) -> Any:
        self.calls.append((method, path, body))

        if method == "GET" and path == "/repos/acme/demo":
            return {
                "id": 42,
                "full_name": "acme/demo",
                "default_branch": "main",
                "html_url": "https://github.com/acme/demo",
            }
        if method == "GET" and path == "/repos/acme/demo/issues/7":
            return {
                "number": 7, "title": "Fix failing build", "body": "CI is red",
                "state": "open", "user": {"id": 10},
                "labels": [{"name": "bug"}, {"name": "ci"}],
            }
        if method == "GET" and path == "/repos/acme/demo/pulls/9":
            return {
                "number": 9, "title": "Fix build", "state": "open",
                "head": {"ref": "fix/build"}, "base": {"ref": "main"},
                "html_url": "https://github.com/acme/demo/pull/9",
            }
        if method == "POST" and path == "/repos/acme/demo/pulls":
            return {
                "number": 9, "title": body["title"], "state": "open",
                "head": {"ref": body["head"]}, "base": {"ref": body["base"]},
                "html_url": "https://github.com/acme/demo/pull/9",
            }
        if method == "POST" and path == "/repos/acme/demo/issues/9/comments":
            return {"id": 1}
        if method == "POST" and path == "/repos/acme/demo/pulls/9/reviews":
            assert body["event"] == "APPROVE"
            return {
                "id": 300, "body": body["body"],
                "html_url": "https://github.com/acme/demo/pull/9#review-300",
                "user": {"id": 11},
            }
        if method == "GET" and path == "/repos/acme/demo/actions/runs":
            assert query["head_sha"] == "deadbeef"
            assert query["branch"] == "fix/build"
            return {
                "workflow_runs": [{
                    "id": 100, "status": "completed", "conclusion": "failure",
                    "head_sha": "deadbeef",
                    "html_url": "https://github.com/acme/demo/actions/runs/100",
                }]
            }
        if method == "GET" and path == "/repos/acme/demo/actions/runs/100":
            return {
                "id": 100, "status": "completed", "conclusion": "failure",
                "head_sha": "deadbeef",
                "html_url": "https://github.com/acme/demo/actions/runs/100",
            }
        if method == "GET" and path == "/repos/acme/demo/actions/runs/100/jobs":
            return {"jobs": [{"id": 201, "name": "test"}, {"id": 202, "name": "lint"}]}
        if method == "POST" and path == "/repos/acme/demo/actions/runs/100/rerun-failed-jobs":
            return None
        if method == "GET" and path == "/repos/acme/demo/actions/runs/100/artifacts":
            return {"artifacts": [{
                "id": 501, "name": "test-report",
                "archive_download_url": "https://api.github.com/artifacts/501",
            }]}
        raise AssertionError(f"Unexpected JSON call: {method} {path} body={body} query={query}")

    async def request_bytes(
        self, method: str, path: str, *, query: Mapping[str, Any] | None = None,
    ) -> bytes:
        if method == "GET" and path == "/repos/acme/demo/actions/jobs/201/logs":
            return b"pytest failed"
        if method == "GET" and path == "/repos/acme/demo/actions/jobs/202/logs":
            return b"ruff passed"
        raise AssertionError(f"Unexpected bytes call: {method} {path}")


async def main() -> None:
    client = FakeGitHubClient()
    secret = b"devopspilot-test-secret"
    scm = GitHubSCMProvider(client, webhook_secret=secret)
    ci = GitHubCIProvider(client)

    assert SCMCapability.REVIEWS in await scm.capabilities()
    assert CICapability.LOGS in await ci.capabilities()

    repo = await scm.get_repository("acme/demo")
    issue = await scm.get_work_item(repo, "7")
    assert issue.labels == ("bug", "ci")

    created = await scm.create_change_request(
        repo, title="Fix build", body="Automated repair",
        source_branch="fix/build", target_branch="main",
    )
    assert created.change_id == "9"
    loaded = await scm.get_change_request(repo, "9")
    assert loaded.source_branch == "fix/build"

    await scm.add_comment(
        CommentSubjectRef(
            repository=repo,
            subject_id="9",
            kind=CommentSubjectKind.CHANGE_REQUEST,
        ),
        body="DevOpsPilot update",
    )
    review = await scm.submit_review(
        repo, change_id="9", state=ReviewState.APPROVE, body="Verified",
    )
    assert review.review_id == "300"

    webhook_payload = json.dumps({
        "repository": {
            "id": 42, "full_name": "acme/demo", "default_branch": "main",
            "html_url": "https://github.com/acme/demo",
        },
        "sender": {"id": 10},
    }, separators=(",", ":")).encode("utf-8")
    signature = "sha256=" + hmac.new(secret, webhook_payload, hashlib.sha256).hexdigest()
    event = await scm.normalize_webhook(
        headers={
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-1",
            "X-Hub-Signature-256": signature,
        },
        body=webhook_payload,
    )
    assert event.event_type == "issues"

    discovered = await ci.list_runs(
        repo, commit_sha="deadbeef", ref="fix/build", status="completed",
    )
    assert discovered[0].run_id == "100"

    run = await ci.get_run(repo, "100")
    logs = [item async for item in ci.stream_logs(run)]
    assert [item.job_name for item in logs] == ["test", "lint"]
    assert logs[0].content == "pytest failed"

    retry = await ci.retry_failed(run)
    assert retry.status == "queued"
    artifacts = await ci.list_artifacts(run)
    assert artifacts[0].name == "test-report"

    print("GITHUB_SCM_ADAPTER_OK")
    print("GITHUB_CI_ADAPTER_OK")
    print("GITHUB_CI_DISCOVERY_OK")
    print("GITHUB_WEBHOOK_SIGNATURE_OK")


if __name__ == "__main__":
    asyncio.run(main())
