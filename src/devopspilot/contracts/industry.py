"""Contracts for Industry Engineering Packs.

Industry Engineering Packs provide vertical domain engineering knowledge,
compliance rules, architecture constraints, review checklists, and test gates
without mutating or hardcoding industry-specific logic into the core framework.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable


class RuleSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKER = "blocker"


@dataclass(frozen=True, slots=True)
class ComplianceRule:
    """A compliance or regulatory engineering rule."""
    rule_id: str
    name: str
    description: str
    severity: RuleSeverity = RuleSeverity.WARNING
    standard: str | None = None  # e.g., "DJCP-2.0", "GB/T-22239"
    remediation_guidance: str | None = None


@dataclass(frozen=True, slots=True)
class ArchitectureConstraint:
    """An architectural constraint for industry software."""
    constraint_id: str
    name: str
    description: str
    allowed_patterns: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewChecklistItem:
    """A domain-specific review checklist item."""
    item_id: str
    category: str
    prompt: str
    must_pass: bool = False


@dataclass(frozen=True, slots=True)
class IndustryTestGate:
    """A specialized automated test gate or verification command."""
    gate_id: str
    name: str
    command: str
    timeout_seconds: int = 120
    required: bool = True


@dataclass(frozen=True, slots=True)
class IndustryEngineeringPack:
    """The canonical metadata and rule container for an industry pack."""
    pack_id: str
    industry: str
    version: str
    title: str
    description: str
    compliance_rules: tuple[ComplianceRule, ...] = ()
    architecture_constraints: tuple[ArchitectureConstraint, ...] = ()
    review_checklist: tuple[ReviewChecklistItem, ...] = ()
    test_gates: tuple[IndustryTestGate, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@runtime_checkable
class IndustryPackRegistry(Protocol):
    """Protocol for discovering, registering, and retrieving Industry Packs."""

    def register_pack(self, pack: IndustryEngineeringPack) -> None:
        """Register an industry engineering pack."""
        ...

    def get_pack(self, pack_id: str) -> IndustryEngineeringPack | None:
        """Retrieve a registered pack by ID."""
        ...

    def list_packs(self, industry: str | None = None) -> tuple[IndustryEngineeringPack, ...]:
        """List all packs or filter by industry."""
        ...
