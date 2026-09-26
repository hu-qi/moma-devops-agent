"""AtomGit implementation of the provider-neutral SCM contract."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping

from devopspilot.contracts.providers import (
    ChangeRequestRef,
    CommentSubjectKind,
    CommentSubjectRef,
    RepositoryRef,
    ReviewRef,
    ReviewState,
    SCMCapability,
    SCMEvent,
    WorkItemRef,
)
from .client import AtomGitAPIClient


_REVIEW_EVENT = {
    ReviewState.COMMENT: "COMMENT",
    ReviewState.APPROVE: "APPROVE",
    ReviewState.REQUEST_CHANGES: "REQUEST_CHANGES",
}


class AtomGitSCMProvider:
    provider_id = "atomgit"

    def __init__(
        self,
        client: AtomGitAPIClient,
        *,
        webhook_secret: str | bytes | None = None,
    ) -> None:
        self._client = client
        if isinstance(webhook_secret, str):
            webhook_secret = webhook_secret.encode("utf-8")
        self._webhook_secret = webhook_secret

    async def capabilities(self) -> frozenset[SCMCapability]:
        return frozenset({
            SCMCapability.ISSUES,
            SCMCapability.CHANGE_REQUESTS,
            SCMCapability.REVIEWS,
            SCMCapability.WEBHOOKS,
            SCMCapability.CHECKS,
            SCMCapability.RELEASES,
        })

    def _verify_webhook(self, headers: Mapping[str, str], body: bytes) -> None:
        if self._webhook_secret is None:
            return
        signature = next(
            (
                v
                for k, v in headers.items()
                if k.lower() in {"x-atomgit-signature", "x-hub-signature-256"}
            ),
            None,
        )
        if not signature:
            raise ValueError("Missing AtomGit signature header")
        prefix = "sha256="
        digest = signature[len(prefix):] if signature.startswith(prefix) else signature
        computed = hmac.new(self._webhook_secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(digest, computed):
            raise ValueError("Invalid AtomGit webhook signature")

    async def normalize_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> SCMEvent:
        self._verify_webhook(headers, body)
        payload = json.loads(body.decode("utf-8"))
        event_type = next(
            (
                v
                for k, v in headers.items()
                if k.lower() in {"x-atomgit-event", "x-github-event"}
            ),
            "unknown",
        )
        delivery_id = next(
            (
                v
                for k, v in headers.items()
                if k.lower() in {"x-atomgit-delivery", "x-github-delivery"}
            ),
            "",
        )
        repo_data = payload.get("repository") or {}
        sender = payload.get("sender") or {}
        repo_ref = RepositoryRef(
            provider_id=self.provider_id,
            repository_id=str(repo_data.get("id", "")),
            full_name=repo_data.get("full_name") or repo_data.get("path") or "",
            default_branch=repo_data.get("default_branch"),
            web_url=repo_data.get("html_url") or repo_data.get("web_url"),
        )
        return SCMEvent(
            provider_id=self.provider_id,
            event_id=str(delivery_id),
            event_type=str(event_type),
            repository=repo_ref,
            actor_id=str(sender.get("id")) if sender.get("id") is not None else None,
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

    async def list_issues(
        self,
        repository: RepositoryRef,
        *,
        state: str = "open",
        limit: int = 20,
    ) -> tuple[WorkItemRef, ...]:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/issues",
            query={"state": state, "per_page": limit},
        )
        return tuple(
            WorkItemRef(
                repository=repository,
                item_id=str(item["number"]),
                title=item["title"],
                state=item.get("state", "open"),
                body=item.get("body") or "",
                author_id=str(item.get("user", {}).get("id")) if item.get("user") else None,
                labels=tuple(l["name"] for l in item.get("labels", []) if isinstance(l, dict) and "name" in l),
            )
            for item in data or []
            if "pull_request" not in item
        )

    async def get_issue(
        self,
        repository: RepositoryRef,
        issue_id: str,
    ) -> WorkItemRef:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/issues/{issue_id}",
        )
        return WorkItemRef(
            repository=repository,
            item_id=str(data["number"]),
            title=data["title"],
            state=data.get("state", "open"),
            body=data.get("body") or "",
            author_id=str(data.get("user", {}).get("id")) if data.get("user") else None,
            labels=tuple(l["name"] for l in data.get("labels", []) if isinstance(l, dict) and "name" in l),
        )

    async def create_change_request(
        self,
        repository: RepositoryRef,
        *,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
        draft: bool = False,
    ) -> ChangeRequestRef:
        data = await self._client.request_json(
            "POST",
            f"/repos/{repository.full_name}/pulls",
            body={
                "title": title,
                "body": body,
                "head": source_branch,
                "base": target_branch,
                "draft": draft,
            },
        )
        return self._map_pull_request(repository, data)

    async def get_change_request(
        self,
        repository: RepositoryRef,
        change_id: str,
    ) -> ChangeRequestRef:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/pulls/{change_id}",
        )
        return self._map_pull_request(repository, data)

    async def add_comment(
        self,
        subject: CommentSubjectRef,
        *,
        body: str,
    ) -> None:
        path = (
            f"/repos/{subject.repository.full_name}/issues/{subject.subject_id}/comments"
        )
        await self._client.request_json("POST", path, body={"body": body})

    async def submit_review(
        self,
        change_request: ChangeRequestRef,
        *,
        state: ReviewState,
        body: str | None = None,
        commit_sha: str | None = None,
    ) -> ReviewRef:
        payload: dict[str, Any] = {"event": _REVIEW_EVENT[state]}
        if body:
            payload["body"] = body
        if commit_sha:
            payload["commit_id"] = commit_sha
        data = await self._client.request_json(
            "POST",
            f"/repos/{change_request.repository.full_name}/pulls/{change_request.change_id}/reviews",
            body=payload,
        )
        return ReviewRef(
            repository=change_request.repository,
            change_id=change_request.change_id,
            review_id=str(data.get("id", "")),
            state=state,
            body=data.get("body") or "",
            web_url=data.get("html_url"),
        )

    def _map_pull_request(
        self,
        repository: RepositoryRef,
        data: Mapping[str, Any],
    ) -> ChangeRequestRef:
        head = data.get("head") or {}
        base = data.get("base") or {}
        merged_at = data.get("merged_at")
        state = "merged" if merged_at else str(data.get("state", "open"))
        return ChangeRequestRef(
            repository=repository,
            change_id=str(data["number"]),
            title=str(data.get("title", "")),
            state=state,
            source_branch=str(head.get("ref", "")),
            target_branch=str(base.get("ref", "")),
            web_url=data.get("html_url"),
        )
