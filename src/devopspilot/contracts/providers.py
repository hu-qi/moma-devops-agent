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


class CICapability(StrEnum):
    RUNS = "runs"
    JOBS = "jobs"
    LOGS = "logs"
    RETRY = "retry"
    TRIGGER = "trigger"
    CANCEL = "cancel"
    ARTIFACTS = "artifacts"


class ReviewState(StrEnum):
    COMMENT = "comment"
    APPROVE = "approve"
    REQUEST_CHANGES = "request-changes"


class CommentSubjectKind(StrEnum):
    WORK_ITEM = "work-item"
    CHANGE_REQUEST = "change-request"


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
class CommentSubjectRef:
    repository: RepositoryRef
    subject_id: str
    kind: CommentSubjectKind


@dataclass(frozen=True, slots=True)
class ReviewRef:
    repository: RepositoryRef
    change_id: str
    review_id: str
    state: ReviewState
    body: str = ""
    author_id: str | None = None
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


@dataclass(frozen=True, slots=True)
class CIArtifactRef:
    run: CIRunRef
    artifact_id: str
    name: str
    download_url: str | None = None


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

    async def get_change_request(
        self,
        repository: RepositoryRef,
        change_id: str,
    ) -> ChangeRequestRef:
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
        subject: CommentSubjectRef,
        *,
        body: str,
    ) -> None:
        ...

    async def submit_review(
        self,
        repository: RepositoryRef,
        *,
        change_id: str,
        state: ReviewState,
        body: str,
    ) -> ReviewRef:
        ...


@runtime_checkable
class CIProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    async def capabilities(self) -> frozenset[CICapability]:
        ...

    async def get_run(
        self,
        repository: RepositoryRef,
        run_id: str,
    ) -> CIRunRef:
        ...

    async def list_runs(
        self,
        repository: RepositoryRef,
        *,
        commit_sha: str | None = None,
        ref: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> tuple[CIRunRef, ...]:
        """Discover runs created automatically by SCM/CI events.

        At least one stable selector (commit_sha or ref) should normally be
        supplied by orchestration when correlating a PR/MR to its CI execution.
        """
        ...

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        ...

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        ...

    async def trigger(
        self,
        repository: RepositoryRef,
        *,
        ref: str,
        workflow_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> CIRunRef:
        ...

    async def cancel(self, run: CIRunRef) -> None:
        ...

    async def list_artifacts(self, run: CIRunRef) -> tuple[CIArtifactRef, ...]:
        ...
