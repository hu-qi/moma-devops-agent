"""Unified delivery report service aligning plan, models, review, tests, CI, SHA, and audit evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from devopspilot.contracts.delivery import DeliveryPhase, DeliveryState
from devopspilot.contracts.planning import ExecutionPlan
from devopspilot.contracts.remediation import RemediationRecord
from devopspilot.contracts.state import StoredDeliveryState


@dataclass(frozen=True, slots=True)
class DeliveryReport:
    """Comprehensive, serializable delivery report adhering to production evidence standards."""

    delivery_id: str
    repository_name: str
    work_item_id: str
    work_item_title: str
    phase: str
    target_branch: str
    version: int = 1
    execution_mode: str = "single_agent"
    execution_rationale: str = ""
    commit_sha: str = ""
    source_branch: str = ""
    leader_model: str = ""
    coding_model: str = ""
    review_model: str = ""
    review_verdict: str = "none"
    review_digest: str = ""
    findings_count: int = 0
    test_summary: str = ""
    ci_status: str = "none"
    ci_run_id: str = ""
    change_request_id: str = ""
    verification_accepted: bool = False
    verification_status: str = "pending"
    degradation_reason: str = ""
    escalation_path: str = ""
    trajectory_id: str = ""
    trajectory_event_count: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    remediation_attempts: int = 0
    remediation_history: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "delivery_id": self.delivery_id,
            "version": self.version,
            "repository": self.repository_name,
            "work_item": {
                "id": self.work_item_id,
                "title": self.work_item_title,
            },
            "phase": self.phase,
            "plan": {
                "mode": self.execution_mode,
                "rationale": self.execution_rationale,
            },
            "execution": {
                "source_branch": self.source_branch,
                "target_branch": self.target_branch,
                "commit_sha": self.commit_sha,
                "change_request_id": self.change_request_id,
                "models": {
                    "leader": self.leader_model,
                    "coding": self.coding_model,
                    "review": self.review_model,
                },
            },
            "review": {
                "verdict": self.review_verdict,
                "diff_digest": self.review_digest,
                "findings_count": self.findings_count,
            },
            "tests": {
                "summary": self.test_summary,
            },
            "ci": {
                "status": self.ci_status,
                "run_id": self.ci_run_id,
            },
            "verification": {
                "accepted": self.verification_accepted,
                "status": self.verification_status,
                "degradation_reason": self.degradation_reason,
                "escalation_path": self.escalation_path,
            },
            "trajectory": {
                "id": self.trajectory_id,
                "event_count": self.trajectory_event_count,
                "model_calls": self.model_calls,
                "tool_calls": self.tool_calls,
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            },
            "remediation": {
                "attempts": self.remediation_attempts,
                "history": list(self.remediation_history),
            },
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def to_markdown(self) -> str:
        status_badge = "✅ VERIFIED CLEAN" if self.verification_status == "verified_clean" else (
            "⚠️ VERIFIED DEGRADED" if self.verification_status == "verified_degraded" else (
                "❌ REJECTED" if self.verification_status == "rejected" else "⏳ IN PROGRESS"
            )
        )

        md = [
            f"# DevOpsPilot Delivery Report: {self.delivery_id}",
            "",
            f"**Outcome**: {status_badge} | **Phase**: `{self.phase}` | **Version**: `{self.version}`",
            "",
            "## 1. Work Item & Delivery Context",
            "",
            f"- **Repository**: `{self.repository_name}`",
            f"- **Work Item**: `#{self.work_item_id}` — {self.work_item_title}",
            f"- **Target Branch**: `{self.target_branch}`",
            f"- **Source Branch**: `{self.source_branch}`",
            f"- **Change Request**: `#{self.change_request_id}`" if self.change_request_id else "- **Change Request**: None",
            "",
            "## 2. Planning & Model Routing",
            "",
            f"- **Execution Mode**: `{self.execution_mode}`",
            f"- **Rationale**: {self.execution_rationale or 'N/A'}",
            f"- **Leader Model**: `{self.leader_model or 'default'}`",
            f"- **Coding Model**: `{self.coding_model or 'default'}`",
            f"- **Review Model**: `{self.review_model or 'default'}`",
            "",
            "## 3. Code Change & Quality Gate Evidence",
            "",
            f"- **Commit SHA**: `{self.commit_sha or 'none'}`",
            f"- **Review Verdict**: `{self.review_verdict.upper()}`",
            f"- **Diff Digest**: `{self.review_digest or 'none'}`",
            f"- **Review Findings**: {self.findings_count} item(s)",
            "",
            "### Verification & CI Execution",
            "",
            f"- **CI Status**: `{self.ci_status}` (Run ID: `{self.ci_run_id or 'none'}`)",
            f"- **Verification Status**: `{self.verification_status}` (Accepted: `{self.verification_accepted}`)",
        ]

        if self.test_summary:
            md.extend([
                "",
                "### Test Execution Summary",
                "",
                "```text",
                self.test_summary[:1500],
                "```",
            ])

        if self.degradation_reason or self.escalation_path:
            md.extend([
                "",
                "## 4. Runtime Degradation & Escalation Audit",
                "",
                f"- **Degradation Reason**: `{self.degradation_reason}`",
                f"- **Recommended Escalation**: `{self.escalation_path}`",
            ])

        md.extend([
            "",
            "## 5. Observability & Trajectory Metrics",
            "",
            f"- **Trajectory ID**: `{self.trajectory_id or 'none'}`",
            f"- **Events Captured**: {self.trajectory_event_count}",
            f"- **Model Calls**: {self.model_calls} | **Tool Calls**: {self.tool_calls}",
            f"- **Token Usage**: {self.input_tokens} prompt + {self.output_tokens} completion",
        ])

        if self.remediation_attempts > 0:
            md.extend([
                "",
                f"## 6. Autonomous Remediation History ({self.remediation_attempts} attempt(s))",
                "",
            ])
            for h in self.remediation_history:
                att = h.get("attempt", "?")
                act = h.get("action", "?")
                out = h.get("outcome", "?")
                sha = h.get("resulting_commit_sha") or "N/A"
                md.append(f"- **Attempt #{att}**: `{act}` -> `{out}` (Commit: `{sha}`)")

        return "\n".join(md)


class DeliveryReportService:
    """Service producing standardized delivery reports from durable states."""

    @classmethod
    def generate_report(
        cls,
        stored: StoredDeliveryState,
        remediation_records: Sequence[RemediationRecord] | None = None,
    ) -> DeliveryReport:
        state = stored.state
        task = state.task
        meta = dict(task.metadata)
        if state.execution:
            meta.update(state.execution.metadata)

        exec_res = state.execution
        review = exec_res.review if exec_res else None
        verif = state.verification

        rem_history: list[dict[str, Any]] = []
        if remediation_records:
            for rec in remediation_records:
                rem_history.append({
                    "attempt": rec.attempt,
                    "action": rec.action.value,
                    "outcome": rec.outcome.value,
                    "summary": rec.summary,
                    "previous_commit_sha": rec.previous_commit_sha,
                    "resulting_commit_sha": rec.resulting_commit_sha,
                    "status": rec.status.value,
                })

        return DeliveryReport(
            delivery_id=stored.delivery_id,
            version=stored.version,
            repository_name=task.repository.full_name,
            work_item_id=task.work_item.item_id,
            work_item_title=task.work_item.title,
            phase=state.phase.value,
            target_branch=task.target_branch,
            execution_mode=meta.get("execution_mode", "single_agent"),
            execution_rationale=meta.get("execution_rationale", ""),
            commit_sha=exec_res.commit_sha if exec_res else "",
            source_branch=exec_res.source_branch if exec_res else "",
            leader_model=meta.get("leader_model", ""),
            coding_model=meta.get("coding_model", ""),
            review_model=meta.get("review_model", ""),
            review_verdict=review.verdict.value if review else "none",
            review_digest=review.diff_digest if review else "",
            findings_count=len(review.findings) if review else 0,
            test_summary=exec_res.test_summary if exec_res else "",
            ci_status=state.ci_run.conclusion or state.ci_run.status if state.ci_run else "none",
            ci_run_id=state.ci_run.run_id if state.ci_run else "",
            change_request_id=state.change_request.change_id if state.change_request else "",
            verification_accepted=verif.accepted if verif else False,
            verification_status=verif.outcome_status if verif else "pending",
            degradation_reason=verif.degradation_reason if verif else meta.get("runtime_degradation_reason", ""),
            escalation_path=verif.escalation_path if verif else "",
            trajectory_id=meta.get("trajectory_id", ""),
            trajectory_event_count=int(meta.get("trajectory_event_count", "0")),
            model_calls=int(meta.get("model_calls", "0")),
            tool_calls=int(meta.get("tool_calls", "0")),
            input_tokens=int(meta.get("input_tokens", "0")),
            output_tokens=int(meta.get("output_tokens", "0")),
            remediation_attempts=len(rem_history),
            remediation_history=tuple(rem_history),
        )
