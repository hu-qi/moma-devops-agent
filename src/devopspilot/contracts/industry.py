"""Contracts for Industry Engineering Packs.

Industry Engineering Packs provide vertical domain engineering knowledge,
compliance rules, architecture constraints, review checklists, and test gates
without mutating or hardcoding industry-specific logic into the core framework.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Protocol, runtime_checkable


class RuleSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class RuleCategory(StrEnum):
    MANDATORY = "mandatory"  # Regulatory/legal hard constraint; failure blocks release
    ADVISORY = "advisory"    # Engineering recommendation / best practice; warning only


class PackConfigurationError(RuntimeError):
    """Raised when an industry engineering pack configuration is missing or invalid."""


@dataclass(frozen=True, slots=True)
class PackRef:
    """Type-safe reference to an exact Industry Engineering Pack version and digest."""

    pack_id: str
    version: str
    digest: str
    industry: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "version": self.version,
            "digest": self.digest,
            "industry": self.industry,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PackRef:
        return cls(
            pack_id=str(data["pack_id"]),
            version=str(data["version"]),
            digest=str(data["digest"]),
            industry=str(data["industry"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True, slots=True)
class ComplianceRule:
    """A compliance or regulatory engineering rule."""
    rule_id: str
    name: str
    description: str
    severity: RuleSeverity = RuleSeverity.WARNING
    category: RuleCategory = RuleCategory.MANDATORY
    standard: str | None = None  # e.g., "DJCP-2.0", "GB/T-22239"
    authority_source: str | None = None  # Specific clause/source, e.g. "GB/T 22239-2019 Cl. 7.1.4.3"
    applicability_condition: str | None = None
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
class GateExecutionResult:
    """Outcome of running a specialized industry test gate command."""
    gate_id: str
    name: str
    required: bool
    passed: bool
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    message: str = ""


class IndustryGateBlockedError(RuntimeError):
    """Raised when an industry verification gate rejects changes."""


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

    def compute_digest(self) -> str:
        """Compute stable SHA256 digest of pack identity, rules, constraints, and gates."""
        repr_data = {
            "pack_id": self.pack_id,
            "industry": self.industry,
            "version": self.version,
            "compliance_rules": [
                {"id": r.rule_id, "name": r.name, "severity": r.severity.value}
                for r in self.compliance_rules
            ],
            "architecture_constraints": [
                {"id": c.constraint_id, "name": c.name}
                for c in self.architecture_constraints
            ],
            "test_gates": [
                {"id": g.gate_id, "command": g.command}
                for g in self.test_gates
            ],
        }
        serialized = json.dumps(repr_data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def pack_ref(self) -> PackRef:
        return PackRef(
            pack_id=self.pack_id,
            version=self.version,
            digest=self.compute_digest(),
            industry=self.industry,
            metadata={"title": self.title},
        )


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
