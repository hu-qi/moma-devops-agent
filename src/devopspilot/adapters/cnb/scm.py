"""CNB OpenAPI mapping to DevOpsPilot SCMProvider."""

from __future__ import annotations

import json
from typing import Any, Mapping

from devopspilot.contracts.providers import (
    ChangeRequestRef, RepositoryRef, ReviewRef, ReviewState,
    SCMCapability, SCMEvent, WorkItemRef,
)
from .client import CNBAPIClient, CNBHTTPClient


_EVENT_MAP = {
    ReviewState.APPROVE: "approve",
    ReviewState.COMMENT: "comment",
    ReviewState.REQUEST_CHANGES: "request_changes",
}
_STATE_MAP = {
    "approved": ReviewState.APPROVE,
    "commented": ReviewState.COMMENT,
    "changes_requested": ReviewState.REQUEST_CHANGES,
}


class CNBSCMProvider:
    provider_id = "cnb"

    def __init__(self, client: CNBAPIClient) -> None:
        self._client = client

    async def capabilities(self) -> frozenset[SCMCapability]:
        # External webhooks are not advertised until a webhook API is live-verified.
        return frozenset({
            SCMCapability.ISSUES,
            SCMCapability.CHANGE_REQUESTS,
            SCMCapability.REVIEWS,
            SCMCapability.CHECKS,
            SCMCapability.RELEASES,
        })

    async def normalize_webhook(self, *, headers: Mapping[str, str], body: bytes) -> SCMEvent:
        # CNB repository-event payload normalization is useful for polling/event bridges
        # even though WEBHOOKS is not currently advertised as a provider capability.
        payload = json.loads(body.decode())
        repo_data = payload.get("repo") or payload.get("repository") or {}
        full_name = repo_data.get("path") or repo_data.get("full_name")
        if not full_name:
            raise ValueError("CNB event has no repository path")
        actor = payload.get("actor") or {}
        return SCMEvent(
            provider_id=self.provider_id,
            event_id=str(payload.get("id", "")),
            event_type=str(payload.get("type", "unknown")),
            repository=RepositoryRef(
                provider_id=self.provider_id,
                repository_id=str(repo_data.get("id", full_name)),
                full_name=full_name,
                web_url=f"https://cnb.cool/{full_name}",
            ),
            actor_id=str(actor.get("id")) if actor.get("id") is not None else None,
            payload=payload,
        )

    async def get_repository(self, repository_id: str) -> RepositoryRef:
        data = await self._client.request_json("GET", f"/{CNBHTTPClient.repo_path(repository_id)}")
        full_name = data.get("slug") or repository_id
        return RepositoryRef(
            provider_id=self.provider_id,
            repository_id=str(data.get("id", full_name)),
            full_name=full_name,
            default_branch=data.get("default_branch") or data.get("main_branch"),
            web_url=data.get("web_url") or f"https://cnb.cool/{full_name}",
        )

    async def get_work_item(self, repository: RepositoryRef, item_id: str) -> WorkItemRef:
        data = await self._client.request_json(
            "GET", f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/issues/{item_id}"
        )
        author = data.get("author") or {}
        labels = tuple(
            str(x.get("name")) for x in data.get("labels", [])
            if isinstance(x, dict) and x.get("name")
        )
        return WorkItemRef(
            repository=repository,
            item_id=str(data["number"]),
            title=data["title"],
            body=data.get("body") or "",
            state=data.get("state", "open"),
            author_id=str(author.get("id")) if author.get("id") is not None else None,
            labels=labels,
        )

    async def get_change_request(self, repository: RepositoryRef, change_id: str) -> ChangeRequestRef:
        data = await self._client.request_json(
            "GET", f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/pulls/{change_id}"
        )
        return self._to_change(repository, data)

    async def create_change_request(
        self, repository: RepositoryRef, *, title: str, body: str,
        source_branch: str, target_branch: str,
    ) -> ChangeRequestRef:
        data = await self._client.request_json(
            "POST",
            f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/pulls",
            body={"title": title, "body": body, "head": source_branch, "base": target_branch},
        )
        return self._to_change(repository, data)

    async def add_comment(
        self, repository: RepositoryRef, *, subject_id: str, body: str,
    ) -> None:
        await self._client.request_json(
            "POST",
            f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/issues/{subject_id}/comments",
            body={"body": body},
        )

    async def submit_review(
        self, repository: RepositoryRef, *, change_id: str,
        state: ReviewState, body: str,
    ) -> ReviewRef:
        path = f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/pulls/{change_id}/reviews"
        result = await self._client.request_json(
            "POST", path, body={"body": body, "event": _EVENT_MAP[state]}
        )
        # Swagger documents 201 without a response schema. Resolve the canonical
        # persisted review from the list endpoint when POST has no body.
        if not isinstance(result, dict) or "id" not in result:
            reviews = await self._client.request_json(
                "GET", path, query={"page": 1, "page_size": 100}
            )
            desired_state = {
                ReviewState.APPROVE: "approved",
                ReviewState.COMMENT: "commented",
                ReviewState.REQUEST_CHANGES: "changes_requested",
            }[state]
            candidates = [
                r for r in (reviews or [])
                if r.get("state") == desired_state and (not body or r.get("body") == body)
            ]
            result = candidates[-1] if candidates else {
                "id": "submitted", "state": desired_state, "body": body
            }
        author = result.get("author") or {}
        return ReviewRef(
            repository=repository,
            change_id=change_id,
            review_id=str(result["id"]),
            state=_STATE_MAP.get(result.get("state"), state),
            body=result.get("body") or body,
            author_id=str(author.get("id")) if author.get("id") is not None else None,
        )

    @staticmethod
    def _branch(ref: Any) -> str:
        if not isinstance(ref, dict):
            return ""
        value = str(ref.get("ref", ""))
        return value.removeprefix("refs/heads/")

    @classmethod
    def _to_change(cls, repository: RepositoryRef, data: Mapping[str, Any]) -> ChangeRequestRef:
        return ChangeRequestRef(
            repository=repository,
            change_id=str(data["number"]),
            title=str(data["title"]),
            source_branch=cls._branch(data.get("head")),
            target_branch=cls._branch(data.get("base")),
            state=str(data.get("state", "open")),
            web_url=f"https://cnb.cool/{repository.full_name}/-/pulls/{data['number']}",
        )
