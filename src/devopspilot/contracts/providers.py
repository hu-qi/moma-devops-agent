"""Provider-neutral integration protocols for DevOpsPilot."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, AsyncIterator, Mapping, Protocol, runtime_checkable

from .model_intelligence import ModelCapability, RoutingDecision, TaskProfile


class SCMCapability(StrEnum):
    ISSUES = "issues"
    CHANGE_REQUESTS = "change-requests"
    REVIEWS = "reviews"
    WEBHOOKS = "webhooks"
    CHECKS = "checks"
    PIPELINES = "pipelines"
    ARTIFACTS = "artifacts"
    RELEASES = "releases"


@dataclass(frozen=True, slots=True)
class RepositoryRef:
    provider_id: str
    repository_id: str
    full_name: str
    default_branch: str | None = None
    web_url: str | None = None


@dataclass(frozen=True, slots=True)
class WorkItemRef:
    repository: RepositoryRef
    item_id: str
    title: str
    body: str = ""
    state: str = "open"
    author_id: str | None = None
    labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChangeRequestRef:
    repository: RepositoryRef
    change_id: str
    title: str
    source_branch: str
    target_branch: str
    state: str
    web_url: str | None = None


@dataclass(frozen=True, slots=True)
class SCMEvent:
    provider_id: str
    event_id: str
    event_type: str
    repository: RepositoryRef
    actor_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CIRunRef:
    provider_id: str
    run_id: str
    repository: RepositoryRef
    status: str
    conclusion: str | None = None
    commit_sha: str | None = None
    web_url: str | None = None


@dataclass(frozen=True, slots=True)
class CIJobLog:
    run: CIRunRef
    job_id: str
    job_name: str
    content: str


@runtime_checkable
class MaaSProvider(Protocol):
    """Control-plane model resolver; invocation belongs to the runtime adapter."""

    @property
    def provider_id(self) -> str:
        ...

    async def resolve(
        self,
        task: TaskProfile,
        capability: ModelCapability,
    ) -> RoutingDecision:
        ...

    async def health(self) -> Mapping[str, Any]:
        ...


@runtime_checkable
class SCMProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    async def capabilities(self) -> frozenset[SCMCapability]:
        ...

    async def normalize_webhook(
        self,
        *,
        headers: Mapping[str, str],
        body: bytes,
    ) -> SCMEvent:
        ...

    async def get_repository(self, repository_id: str) -> RepositoryRef:
        ...

    async def get_work_item(
        self,
        repository: RepositoryRef,
        item_id: str,
    ) -> WorkItemRef:
        ...

    async def create_change_request(
        self,
        repository: RepositoryRef,
        *,
        title: str,
        body: str,
        source_branch: str,
        target_branch: str,
    ) -> ChangeRequestRef:
        ...

    async def add_comment(
        self,
        repository: RepositoryRef,
        *,
        subject_id: str,
        body: str,
    ) -> None:
        ...


@runtime_checkable
class CIProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    async def get_run(
        self,
        repository: RepositoryRef,
        run_id: str,
    ) -> CIRunRef:
        ...

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        ...

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        ...
