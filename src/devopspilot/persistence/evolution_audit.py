"""SQLite audit store for governed evolution candidates and decisions."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from devopspilot.contracts.evolution import (
    ApprovalState,
    ArtifactKind,
    ArtifactVersion,
    BenchmarkObservation,
    EvolutionCandidate,
    EvolutionEvidence,
    PromotionDecision,
    TeamPatternCreationDecision,
    TeamPatternCreationProposal,
)


class EvolutionAuditConflict(RuntimeError):
    """Raised when an immutable audit identity is reused with different data."""


@dataclass(frozen=True, slots=True)
class StoredEvolutionEvidence:
    candidate_id: str
    version: int
    evidence: EvolutionEvidence


@dataclass(frozen=True, slots=True)
class StoredPromotionDecision:
    candidate_id: str
    version: int
    decision: PromotionDecision


@dataclass(frozen=True, slots=True)
class StoredTeamPatternCreationDecision:
    proposal_id: str
    version: int
    decision: TeamPatternCreationDecision


class SQLiteEvolutionAuditStore:
    """Append-oriented audit storage for the self-evolution lifecycle.

    Candidate identity is immutable. Benchmark evidence and promotion decisions
    are versioned histories so reevaluation never overwrites prior evidence.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path)
        db.row_factory = sqlite3.Row
        return db

    def _init_db(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS evolution_candidate (
                    candidate_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS team_pattern_proposal (
                    proposal_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS team_pattern_proposal_decision (
                    proposal_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(proposal_id, version)
                );

                CREATE TABLE IF NOT EXISTS evolution_evidence (
                    candidate_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, version)
                );

                CREATE TABLE IF NOT EXISTS evolution_decision (
                    candidate_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY(candidate_id, version)
                );
                """
            )

    async def save_team_pattern_proposal(
        self,
        proposal: TeamPatternCreationProposal,
    ) -> TeamPatternCreationProposal:
        return await asyncio.to_thread(
            self._save_team_pattern_proposal_sync,
            proposal,
        )

    def _save_team_pattern_proposal_sync(
        self,
        proposal: TeamPatternCreationProposal,
    ) -> TeamPatternCreationProposal:
        payload = _json(_encode_team_pattern_proposal(proposal))
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM team_pattern_proposal WHERE proposal_id = ?",
                (proposal.proposal_id,),
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO team_pattern_proposal(proposal_id, payload) VALUES (?, ?)",
                    (proposal.proposal_id, payload),
                )
                return proposal
            if row["payload"] != payload:
                raise EvolutionAuditConflict(
                    f"team pattern proposal {proposal.proposal_id!r} "
                    "already exists with different content"
                )
        return proposal

    async def load_team_pattern_proposal(
        self,
        proposal_id: str,
    ) -> TeamPatternCreationProposal | None:
        return await asyncio.to_thread(
            self._load_team_pattern_proposal_sync,
            proposal_id,
        )

    def _load_team_pattern_proposal_sync(
        self,
        proposal_id: str,
    ) -> TeamPatternCreationProposal | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM team_pattern_proposal WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return _decode_team_pattern_proposal(json.loads(row["payload"]))

    async def append_team_pattern_creation_decision(
        self,
        decision: TeamPatternCreationDecision,
    ) -> StoredTeamPatternCreationDecision:
        proposal = await self.load_team_pattern_proposal(decision.proposal_id)
        if proposal is None:
            raise EvolutionAuditConflict(
                f"unknown team pattern proposal {decision.proposal_id!r}"
            )
        return await asyncio.to_thread(
            self._append_team_pattern_creation_decision_sync,
            decision,
        )

    def _append_team_pattern_creation_decision_sync(
        self,
        decision: TeamPatternCreationDecision,
    ) -> StoredTeamPatternCreationDecision:
        version = self._append_versioned(
            table="team_pattern_proposal_decision",
            candidate_id=decision.proposal_id,
            payload=_json(_encode_team_pattern_creation_decision(decision)),
        )
        return StoredTeamPatternCreationDecision(
            proposal_id=decision.proposal_id,
            version=version,
            decision=decision,
        )

    async def load_latest_team_pattern_creation_decision(
        self,
        proposal_id: str,
    ) -> StoredTeamPatternCreationDecision | None:
        row = await asyncio.to_thread(
            self._load_latest_sync,
            "team_pattern_proposal_decision",
            proposal_id,
        )
        if row is None:
            return None
        return StoredTeamPatternCreationDecision(
            proposal_id=proposal_id,
            version=int(row["version"]),
            decision=_decode_team_pattern_creation_decision(
                json.loads(row["payload"])
            ),
        )

    async def save_candidate(self, candidate: EvolutionCandidate) -> EvolutionCandidate:
        return await asyncio.to_thread(self._save_candidate_sync, candidate)

    def _save_candidate_sync(self, candidate: EvolutionCandidate) -> EvolutionCandidate:
        payload = _json(_encode_candidate(candidate))
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM evolution_candidate WHERE candidate_id = ?",
                (candidate.candidate_id,),
            ).fetchone()
            if row is None:
                db.execute(
                    "INSERT INTO evolution_candidate(candidate_id, payload) VALUES (?, ?)",
                    (candidate.candidate_id, payload),
                )
                return candidate
            if row["payload"] != payload:
                raise EvolutionAuditConflict(
                    f"candidate {candidate.candidate_id!r} already exists with different content"
                )
        return candidate

    async def load_candidate(self, candidate_id: str) -> EvolutionCandidate | None:
        return await asyncio.to_thread(self._load_candidate_sync, candidate_id)

    def _load_candidate_sync(self, candidate_id: str) -> EvolutionCandidate | None:
        with self._connect() as db:
            row = db.execute(
                "SELECT payload FROM evolution_candidate WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
        return None if row is None else _decode_candidate(json.loads(row["payload"]))

    async def append_evidence(self, evidence: EvolutionEvidence) -> StoredEvolutionEvidence:
        return await asyncio.to_thread(self._append_evidence_sync, evidence)

    def _append_evidence_sync(self, evidence: EvolutionEvidence) -> StoredEvolutionEvidence:
        version = self._append_versioned(
            table="evolution_evidence",
            candidate_id=evidence.candidate_id,
            payload=_json(_encode_evidence(evidence)),
        )
        return StoredEvolutionEvidence(evidence.candidate_id, version, evidence)

    async def load_latest_evidence(
        self,
        candidate_id: str,
    ) -> StoredEvolutionEvidence | None:
        row = await asyncio.to_thread(
            self._load_latest_sync,
            "evolution_evidence",
            candidate_id,
        )
        if row is None:
            return None
        return StoredEvolutionEvidence(
            candidate_id=candidate_id,
            version=int(row["version"]),
            evidence=_decode_evidence(json.loads(row["payload"])),
        )

    async def append_decision(
        self,
        decision: PromotionDecision,
    ) -> StoredPromotionDecision:
        return await asyncio.to_thread(self._append_decision_sync, decision)

    def _append_decision_sync(
        self,
        decision: PromotionDecision,
    ) -> StoredPromotionDecision:
        # A production approval is only meaningful for a gate-passed candidate.
        if decision.state is ApprovalState.APPROVED and not decision.evidence.gate_passed:
            raise EvolutionAuditConflict(
                "cannot record APPROVED for a candidate that failed the automated gate"
            )
        version = self._append_versioned(
            table="evolution_decision",
            candidate_id=decision.candidate_id,
            payload=_json(_encode_decision(decision)),
        )
        return StoredPromotionDecision(decision.candidate_id, version, decision)

    async def load_latest_decision(
        self,
        candidate_id: str,
    ) -> StoredPromotionDecision | None:
        row = await asyncio.to_thread(
            self._load_latest_sync,
            "evolution_decision",
            candidate_id,
        )
        if row is None:
            return None
        return StoredPromotionDecision(
            candidate_id=candidate_id,
            version=int(row["version"]),
            decision=_decode_decision(json.loads(row["payload"])),
        )

    def _append_versioned(self, *, table: str, candidate_id: str, payload: str) -> int:
        if table not in {
            "team_pattern_proposal_decision",
            "evolution_evidence",
            "evolution_decision",
        }:
            raise ValueError(f"unsupported audit table: {table}")
        key_column = (
            "proposal_id"
            if table == "team_pattern_proposal_decision"
            else "candidate_id"
        )
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                f"SELECT MAX(version) AS version FROM {table} "
                f"WHERE {key_column} = ?",
                (candidate_id,),
            ).fetchone()
            version = int(row["version"] or 0) + 1
            db.execute(
                f"INSERT INTO {table}({key_column}, version, payload) "
                "VALUES (?, ?, ?)",
                (candidate_id, version, payload),
            )
        return version

    def _load_latest_sync(self, table: str, candidate_id: str) -> sqlite3.Row | None:
        if table not in {
            "team_pattern_proposal_decision",
            "evolution_evidence",
            "evolution_decision",
        }:
            raise ValueError(f"unsupported audit table: {table}")
        key_column = (
            "proposal_id"
            if table == "team_pattern_proposal_decision"
            else "candidate_id"
        )
        with self._connect() as db:
            return db.execute(
                f"SELECT version, payload FROM {table} "
                f"WHERE {key_column} = ? ORDER BY version DESC LIMIT 1",
                (candidate_id,),
            ).fetchone()


def _json(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _encode_artifact(value: ArtifactVersion) -> dict[str, Any]:
    return {
        "artifact_id": value.artifact_id,
        "kind": value.kind.value,
        "version": value.version,
        "content": value.content,
        "metadata": dict(value.metadata),
    }


def _decode_artifact(value: dict[str, Any]) -> ArtifactVersion:
    return ArtifactVersion(
        artifact_id=value["artifact_id"],
        kind=ArtifactKind(value["kind"]),
        version=value["version"],
        content=value["content"],
        metadata=value.get("metadata", {}),
    )


def _encode_team_pattern_proposal(
    value: TeamPatternCreationProposal,
) -> dict[str, Any]:
    return {
        "proposal_id": value.proposal_id,
        "proposal_key": value.proposal_key,
        "reusable_guidance": value.reusable_guidance,
        "evidence": list(value.evidence),
        "source_opportunity_ids": list(value.source_opportunity_ids),
        "provider_id": value.provider_id,
        "approval_payload": dict(value.approval_payload),
        "production_write": value.production_write,
    }


def _decode_team_pattern_proposal(
    value: dict[str, Any],
) -> TeamPatternCreationProposal:
    return TeamPatternCreationProposal(
        proposal_id=value["proposal_id"],
        proposal_key=value["proposal_key"],
        reusable_guidance=value["reusable_guidance"],
        evidence=tuple(value.get("evidence", [])),
        source_opportunity_ids=tuple(value.get("source_opportunity_ids", [])),
        provider_id=value["provider_id"],
        approval_payload=value.get("approval_payload", {}),
        production_write=bool(value.get("production_write", False)),
    )


def _encode_team_pattern_creation_decision(
    value: TeamPatternCreationDecision,
) -> dict[str, Any]:
    return {
        "proposal_id": value.proposal_id,
        "state": value.state.value,
        "decided_by": value.decided_by,
        "reason": value.reason,
    }


def _decode_team_pattern_creation_decision(
    value: dict[str, Any],
) -> TeamPatternCreationDecision:
    return TeamPatternCreationDecision(
        proposal_id=value["proposal_id"],
        state=ApprovalState(value["state"]),
        decided_by=value.get("decided_by", ""),
        reason=value.get("reason", ""),
    )


def _encode_candidate(value: EvolutionCandidate) -> dict[str, Any]:
    return {
        "candidate_id": value.candidate_id,
        "artifact": _encode_artifact(value.artifact),
        "base_artifact_id": value.base_artifact_id,
        "base_version": value.base_version,
        "provider_id": value.provider_id,
        "change_summary": value.change_summary,
        "source_trajectory_ids": list(value.source_trajectory_ids),
        "metadata": dict(value.metadata),
    }


def _decode_candidate(value: dict[str, Any]) -> EvolutionCandidate:
    return EvolutionCandidate(
        candidate_id=value["candidate_id"],
        artifact=_decode_artifact(value["artifact"]),
        base_artifact_id=value["base_artifact_id"],
        base_version=value["base_version"],
        provider_id=value["provider_id"],
        change_summary=value["change_summary"],
        source_trajectory_ids=tuple(value.get("source_trajectory_ids", [])),
        metadata=value.get("metadata", {}),
    )


def _encode_observation(value: BenchmarkObservation) -> dict[str, Any]:
    return {
        "case_id": value.case_id,
        "task_success": value.task_success,
        "regression_count": value.regression_count,
        "duration_ms": value.duration_ms,
        "tool_calls": value.tool_calls,
        "input_tokens": value.input_tokens,
        "output_tokens": value.output_tokens,
        "runtime_clean_completion": value.runtime_clean_completion,
    }


def _decode_observation(value: dict[str, Any]) -> BenchmarkObservation:
    return BenchmarkObservation(**value)


def _encode_evidence(value: EvolutionEvidence) -> dict[str, Any]:
    return {
        "candidate_id": value.candidate_id,
        "baseline": [_encode_observation(x) for x in value.baseline],
        "candidate": [_encode_observation(x) for x in value.candidate],
        "improved_metrics": list(value.improved_metrics),
        "regressions": list(value.regressions),
        "gate_passed": value.gate_passed,
    }


def _decode_evidence(value: dict[str, Any]) -> EvolutionEvidence:
    return EvolutionEvidence(
        candidate_id=value["candidate_id"],
        baseline=tuple(_decode_observation(x) for x in value.get("baseline", [])),
        candidate=tuple(_decode_observation(x) for x in value.get("candidate", [])),
        improved_metrics=tuple(value.get("improved_metrics", [])),
        regressions=tuple(value.get("regressions", [])),
        gate_passed=bool(value["gate_passed"]),
    )


def _encode_decision(value: PromotionDecision) -> dict[str, Any]:
    return {
        "candidate_id": value.candidate_id,
        "state": value.state.value,
        "evidence": _encode_evidence(value.evidence),
        "rollback_version": value.rollback_version,
        "reason": value.reason,
    }


def _decode_decision(value: dict[str, Any]) -> PromotionDecision:
    return PromotionDecision(
        candidate_id=value["candidate_id"],
        state=ApprovalState(value["state"]),
        evidence=_decode_evidence(value["evidence"]),
        rollback_version=value["rollback_version"],
        reason=value.get("reason", ""),
    )
