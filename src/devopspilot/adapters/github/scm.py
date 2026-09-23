"""GitHub implementation of the provider-neutral SCM contract."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Mapping

from devopspilot.contracts.providers import (
    ChangeRequestRef,
    RepositoryRef,
    ReviewRef,
    ReviewState,
    SCMCapability,
    SCMEvent,
    SCMProvider,
    WorkItemRef,
)

from .client import GitHubAPIClient


_REVIEW_EVENT = {
    ReviewState.COMMENT: "COMMENT",
    ReviewState.APPROVE: "APPROVE",
    ReviewState.REQUEST_CHANGES: "REQUEST_CHANGES",
}


class GitHubSCMProvider:
    provider_id = "github"

    def __init__(
        self,
        client: GitHubAPIClient,
        *,
        webhook_secret: str | bytes | None = None,
    ) -> None:
        self._client = client
        if isinstance(webhook_secret, str):
            webhook_secret = webhook_secret.encode("utf-8")
        self._webhook_secret = webhook_secret

    async def capabilities(self) -> frozenset[SCMCapability]:
        return frozenset(
            {
                SCMCapability.ISSUES,
                SCMCapability.CHANGE_REQUESTS,
                SCMCapability.REVIEWS,
                SCMCapability.WEBHOOKS,
                SCMCapability.CHECKS,
                SCMCapability.RELEASES,
            }
        )

    def _verify_webhook(self, headers: Mapping[str, str], body: bytes) -> None:
        if self._webhook_secret is None:
            return
        signature = next(
            (value for key, value in headers.items() if key.lower() == "x-hub-signature-256"),
            "",
        )
        if not signature.startswith("sha256="):
            raise ValueError("Missing GitHub X-Hub-Signature-256")
        expected = "sha256=" + hmac.new(
            self._webhook_secret,
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid GitHub webhook signature")

    async def normalize_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> SCMEvent:
        self._verify_webhook(headers, body)
        payload = json.loads(body.decode("utf-8"))
        repository_data = payload.get("repository") or {}
        full_name = repository_data.get("full_name")
        if not full_name:
            raise ValueError("GitHub webhook payload has no repository.full_name")

        event_type = next(
            (value for key, value in headers.items() if key.lower() == "x-github-event"),
            "unknown",
        )
        delivery_id = next(
            (value for key, value in headers.items() if key.lower() == "x-github-delivery"),
            "",
        )
        actor = payload.get("sender") or {}

        repository = RepositoryRef(
            provider_id=self.provider_id,
            repository_id=str(repository_data.get("id", full_name)),
            full_name=full_name,
            default_branch=repository_data.get("default_branch"),
            web_url=repository_data.get("html_url"),
        )
        return SCMEvent(
            provider_id=self.provider_id,
            event_id=delivery_id or f"{event_type}:{full_name}",
            event_type=event_type,
            repository=repository,
            actor_id=str(actor.get("id")) if actor.get("id") is not None else None,
            payload=payload,
        )

    async def get_repository(self, repository_id: str) -> RepositoryRef:
        data = await self._client.request_json("GET", f"/repos/{repository_id}")
        return RepositoryRef(
            provider_id=self.provider_id,
            repository_id=str(data["id"]),
            full_name=data["full_name"],
            default_branch=data.get("default_branch"),
            web_url=data.get("html_url"),
        )

    async def get_work_item(
        self,
        repository: RepositoryRef,
        item_id: str,
    ) -> WorkItemRef:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/issues/{item_id}",
        )
        user = data.get("user") or {}
        labels = tuple(
            label.get("name", "")
            for label in data.get("labels", [])
            if isinstance(label, dict) and label.get("name")
        )
        return WorkItemRef(
            repository=repository,
            item_id=str(data["number"]),
            title=data["title"],
            body=data.get("body") or "",
            state=data.get("state", "open"),
            author_id=str(user["id"]) if user.get("id") is not None else None,
            labels=labels,
        )

    async def get_change_request(
        self,
        repository: RepositoryRef,
        change_id: str,
    ) -> ChangeRequestRef:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/pulls/{change_id}",
        )
        return self._to_change_request(repository, data)

    async def create_change_request(
        self,
        repository: RepositoryRef,
        *,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
    ) -> ChangeRequestRef:
        data = await self._client.request_json(
            "POST",
            f"/repos/{repository.full_name}/pulls",
            body={
                "title": title,
                "body": body,
                "head": source_branch,
                "base": target_branch,
            },
        )
        return self._to_change_request(repository, data)

    async def add_comment(
        self,
        repository: RepositoryRef,
        *,
        subject_id: str,
        body: str,
    ) -> None:
        await self._client.request_json(
            "POST",
            f"/repos/{repository.full_name}/issues/{subject_id}/comments",
            body={"body": body},
        )

    async def submit_review(
        self,
        repository: RepositoryRef,
        *,
        change_id: str,
        state: ReviewState,
        body: str,
    ) -> ReviewRef:
        data = await self._client.request_json(
            "POST",
            f"/repos/{repository.full_name}/pulls/{change_id}/reviews",
            body={
                "body": body,
                "event": _REVIEW_EVENT[state],
            },
        )
        user = data.get("user") or {}
        return ReviewRef(
            repository=repository,
            change_id=change_id,
            review_id=str(data["id"]),
            state=state,
            body=data.get("body") or body,
            author_id=str(user["id"]) if user.get("id") is not None else None,
            web_url=data.get("html_url"),
        )

    @staticmethod
    def _to_change_request(
        repository: RepositoryRef,
        data: Mapping[str, object],
    ) -> ChangeRequestRef:
        head = data.get("head") if isinstance(data.get("head"), dict) else {}
        base = data.get("base") if isinstance(data.get("base"), dict) else {}
        return ChangeRequestRef(
            repository=repository,
            change_id=str(data["number"]),
            title=str(data["title"]),
            source_branch=str(head.get("ref", "")),
            target_branch=str(base.get("ref", "")),
            state=str(data.get("state", "open")),
            web_url=str(data["html_url"]) if data.get("html_url") else None,
        )


assert isinstance(GitHubSCMProvider, type)
