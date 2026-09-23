"""Canonical contracts for provider-neutral software delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Mapping, Protocol, runtime_checkable

from .providers import ChangeRequestRef, CIJobLog, CIRunRef, RepositoryRef, WorkItemRef


class DeliveryPhase(StrEnum):
    RECEIVED = "received"
    EXECUTED = "executed"
    CHANGE_OPENED = "change-opened"
    CI_PENDING = "ci-pending"
    CI_FAILED = "ci-failed"
    CI_PASSED = "ci-passed"
    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class DeliveryTask:
    repository: RepositoryRef
    work_item: WorkItemRef
    target_branch: str
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Result produced by an Agent/runtime execution.

    published=True means the source branch/commit is already visible to the
    SCM provider and can safely be used to create a PR/MR.
    """

    source_branch: str
    commit_sha: str
    summary: str
    published: bool
    test_summary: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    accepted: bool
    summary: str
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DeliveryState:
    task: DeliveryTask
    phase: DeliveryPhase
    execution: ExecutionResult | None = None
    change_request: ChangeRequestRef | None = None
    ci_run: CIRunRef | None = None
    ci_logs: tuple[CIJobLog, ...] = ()
    verification: VerificationResult | None = None


@runtime_checkable
class TaskExecutor(Protocol):
    """Runtime-neutral execution port."""

    async def execute(self, task: DeliveryTask) -> ExecutionResult:
        ...


@runtime_checkable
class DeliveryVerifier(Protocol):
    async def verify(self, state: DeliveryState) -> VerificationResult:
        ...
