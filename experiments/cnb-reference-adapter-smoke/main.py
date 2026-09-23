"""Credential-free behavior smoke for CNB SCM/CI adapters."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from devopspilot.adapters.cnb import CNBCIProvider, CNBSCMProvider
from devopspilot.contracts.providers import (
    CICapability,
    CommentSubjectKind,
    CommentSubjectRef,
    ReviewState,
    SCMCapability,
)


class FakeCNBClient:
    async def request_json(self, method: str, path: str, *, body=None, query=None) -> Any:
        if method == "GET" and path == "/acme/demo":
            return {"id":"42","slug":"acme/demo","default_branch":"main","web_url":"https://cnb.cool/acme/demo"}
        if method == "GET" and path == "/acme/demo/-/issues/7":
            return {"number":"7","title":"Fix CI","body":"red","state":"open","author":{"id":"10"},"labels":[{"name":"bug"}]}
        if method == "GET" and path == "/acme/demo/-/pulls/9":
            return {"number":"9","title":"Fix CI","state":"open","head":{"ref":"refs/heads/fix/ci"},"base":{"ref":"refs/heads/main"}}
        if method == "POST" and path == "/acme/demo/-/pulls":
            return {"number":"9","title":body["title"],"state":"open","head":{"ref":"refs/heads/"+body["head"]},"base":{"ref":"refs/heads/"+body["base"]}}
        if method == "POST" and path == "/acme/demo/-/issues/7/comments":
            return {"id":"issue-comment"}
        if method == "POST" and path == "/acme/demo/-/pulls/9/comments":
            return {"id":"pr-comment"}
        if method == "POST" and path == "/acme/demo/-/pulls/9/reviews":
            assert body["event"] == "approve"
            return None
        if method == "GET" and path == "/acme/demo/-/pulls/9/reviews":
            return [{"id":"r1","state":"approved","body":"Verified","author":{"id":"11"}}]
        if method == "GET" and path == "/acme/demo/-/build/logs":
            assert query["sha"] == "deadbeef"
            assert query["sourceRef"] == "fix/ci"
            return {"data":[{
                "sn":"100","status":"error","sha":"deadbeef",
                "sourceRef":"fix/ci",
                "buildLogUrl":"https://cnb.cool/acme/demo/-/build/100",
            }],"total":1}
        if method == "GET" and path == "/acme/demo/-/build/status/100":
            return {"status":"error","pipelinesStatus":{"p1":{"id":"p1","name":"main","status":"error","stages":[{"id":"s1","name":"test","status":"error"}]}}}
        if method == "GET" and path == "/acme/demo/-/build/logs/stage/100/p1/s1":
            return {"id":"s1","name":"test","status":"error","content":["pytest failed"],"error":"1 failed"}
        if method == "POST" and path == "/acme/demo/-/build/start":
            return {"sn":"101","success":True,"buildLogUrl":"https://cnb.cool/acme/demo/-/build/101"}
        if method == "POST" and path == "/acme/demo/-/build/stop/100":
            return {"success":True,"sn":"100"}
        raise AssertionError(f"unexpected {method} {path} body={body} query={query}")


async def main() -> None:
    client = FakeCNBClient()
    scm = CNBSCMProvider(client)
    ci = CNBCIProvider(client)

    assert SCMCapability.CHANGE_REQUESTS in await scm.capabilities()
    assert SCMCapability.WEBHOOKS not in await scm.capabilities()
    assert CICapability.LOGS in await ci.capabilities()
    assert CICapability.RETRY not in await ci.capabilities()

    repo = await scm.get_repository("acme/demo")
    issue = await scm.get_work_item(repo, "7")
    assert issue.title == "Fix CI"

    pr = await scm.create_change_request(
        repo, title="Fix CI", body="", source_branch="fix/ci", target_branch="main",
    )
    assert pr.source_branch == "fix/ci"

    await scm.add_comment(
        CommentSubjectRef(repo, "7", CommentSubjectKind.WORK_ITEM),
        body="Issue update",
    )
    await scm.add_comment(
        CommentSubjectRef(repo, "9", CommentSubjectKind.CHANGE_REQUEST),
        body="PR update",
    )

    review = await scm.submit_review(
        repo, change_id="9", state=ReviewState.APPROVE, body="Verified",
    )
    assert review.review_id == "r1"

    event = await scm.normalize_webhook(headers={}, body=json.dumps({
        "id":"e1","type":"IssueEvent","repo":{"id":"42","path":"acme/demo"},"actor":{"id":"10"}
    }).encode())
    assert event.event_type == "IssueEvent"

    discovered = await ci.list_runs(
        repo, commit_sha="deadbeef", ref="fix/ci", status="error",
    )
    assert discovered[0].run_id == "100"
    assert discovered[0].commit_sha == "deadbeef"

    run = await ci.get_run(repo, "100")
    assert run.conclusion == "failure"
    logs = [x async for x in ci.stream_logs(run)]
    assert logs[0].job_name == "test" and "pytest failed" in logs[0].content

    new_run = await ci.trigger(repo, ref="main", inputs={"MODE":"test"})
    assert new_run.run_id == "101"
    await ci.cancel(run)

    try:
        await ci.retry_failed(run)
    except NotImplementedError:
        pass
    else:
        raise AssertionError("retry must remain unsupported until CNB exposes it")

    print("CNB_SCM_ADAPTER_OK")
    print("CNB_CI_ADAPTER_OK")
    print("CNB_CI_DISCOVERY_OK")
    print("CNB_COMMENT_ROUTING_OK")


if __name__ == "__main__":
    asyncio.run(main())
