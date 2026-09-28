"""Execution plan contracts for Single Agent First and Agent Team orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ExecutionMode(StrEnum):
    SINGLE_AGENT = "single_agent"
    AGENT_TEAM = "agent_team"


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Explicit, serializable execution plan determining execution mode, models, and boundaries."""

    mode: ExecutionMode
    rationale: str
    risk_level: str = "medium"
    context_summary: str = ""
    allowed_paths: tuple[str, ...] = ()
    forbidden_paths: tuple[str, ...] = ()
    test_command: str = ""
    budget_limit: int = 3
    require_review: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "rationale": self.rationale,
            "risk_level": self.risk_level,
            "context_summary": self.context_summary,
            "allowed_paths": list(self.allowed_paths),
            "forbidden_paths": list(self.forbidden_paths),
            "test_command": self.test_command,
            "budget_limit": self.budget_limit,
            "require_review": self.require_review,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExecutionPlan:
        return cls(
            mode=ExecutionMode(data.get("mode", ExecutionMode.SINGLE_AGENT.value)),
            rationale=str(data.get("rationale", "")),
            risk_level=str(data.get("risk_level", "medium")),
            context_summary=str(data.get("context_summary", "")),
            allowed_paths=tuple(data.get("allowed_paths", ())),
            forbidden_paths=tuple(data.get("forbidden_paths", ())),
            test_command=str(data.get("test_command", "")),
            budget_limit=int(data.get("budget_limit", 3)),
            require_review=bool(data.get("require_review", True)),
            metadata=dict(data.get("metadata", {})),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> ExecutionPlan:
        return cls.from_dict(json.loads(raw))
