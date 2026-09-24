"""Domain contracts for governed self-evolution."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable


class ArtifactKind(StrEnum):
    SKILL = "skill"
    SKILL_EXPERIENCE = "skill-experience"
    PROMPT = "prompt"
    ROUTING_POLICY = "routing-policy"
    TEAM_PATTERN = "team-pattern"
    TOOL_STRATEGY = "tool-strategy"


class ApprovalState(StrEnum):
    PENDING_HUMAN = "pending-human"
    APPROVED = "approved"
    REJECTED = "rejected"


class OpportunityPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class ArtifactVersion:
    artifact_id: str
    kind: ArtifactKind
    version: str
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class EvolutionSignalEvidence:
    signal_type: str
    section: str
    excerpt: str
    source: str
    trajectory_id: str | None = None
    tool_name: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvolutionOpportunity:
    opportunity_id: str
    target_kind: ArtifactKind
    objective: str
    source_trajectory_ids: tuple[str, ...]
    signals: tuple[EvolutionSignalEvidence, ...]
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    auto_candidate_allowed: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TeamPatternCreationProposal:
    proposal_id: str
    proposal_key: str
    reusable_guidance: str
    evidence: tuple[str, ...]
    source_opportunity_ids: tuple[str, ...]
    provider_id: str
    approval_payload: Mapping[str, Any] = field(default_factory=dict)
    production_write: bool = False


@runtime_checkable
class TeamPatternCreationProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    async def propose_creation(
        self,
        opportunities: tuple[EvolutionOpportunity, ...],
    ) -> TeamPatternCreationProposal:
        ...





@dataclass(frozen=True, slots=True)
class TeamPatternCreationDecision:
    proposal_id: str
    state: ApprovalState
    decided_by: str = ""
    reason: str = ""


@runtime_checkable
class TeamPatternCandidateProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    async def generate_candidate(
        self,
        proposal: TeamPatternCreationProposal,
        decision: TeamPatternCreationDecision,
    ) -> EvolutionCandidate:
        ...


@dataclass(frozen=True, slots=True)
class EvolutionRequest:
    request_id: str
    base_artifact: ArtifactVersion
    objective: str
    source_trajectory_ids: tuple[str, ...]
    evaluation_cases: tuple[str, ...]
    signals: tuple[EvolutionSignalEvidence, ...] = ()
    constraints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EvolutionCandidate:
    candidate_id: str
    artifact: ArtifactVersion
    base_artifact_id: str
    base_version: str
    provider_id: str
    change_summary: str
    source_trajectory_ids: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    case_id: str
    task_success: bool
    regression_count: int = 0
    duration_ms: int | None = None
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    runtime_clean_completion: bool | None = None


@dataclass(frozen=True, slots=True)
class EvolutionEvidence:
    candidate_id: str
    baseline: tuple[BenchmarkObservation, ...]
    candidate: tuple[BenchmarkObservation, ...]
    improved_metrics: tuple[str, ...]
    regressions: tuple[str, ...]
    gate_passed: bool


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    candidate_id: str
    state: ApprovalState
    evidence: EvolutionEvidence
    rollback_version: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class RollbackDecision:
    artifact_id: str
    target_version: str | None
    state: ApprovalState
    decided_by: str
    reason: str = ""


@runtime_checkable
class EvolutionProvider(Protocol):
    @property
    def provider_id(self) -> str:
        ...

    async def generate_candidate(
        self,
        request: EvolutionRequest,
    ) -> EvolutionCandidate:
        ...
