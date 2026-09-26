"""Autonomous delivery control plane with bounded CI remediation."""

from __future__ import annotations

from dataclasses import dataclass, replace

from devopspilot.contracts.delivery import (
    DeliveryPhase,
    DeliveryState,
    VerificationResult,
)
from devopspilot.contracts.providers import CICapability, CIProvider
from devopspilot.contracts.remediation import (
    CIFailureAnalysis,
    CIFailureAnalyzer,
    CIFailureKind,
    RemediationAction,
    RemediationExecutor,
    RemediationLedger,
    RemediationOutcome,
    RemediationRecord,
)


@dataclass(frozen=True, slots=True)
class RemediationDecision:
    action: RemediationAction
    reason: str


class RuleBasedCIFailureAnalyzer:
    """Conservative first-pass classifier before Agent remediation."""

    _INFRA_MARKERS = (
        "timed out",
        "timeout",
        "rate limit",
        "connection reset",
        "connection refused",
        "temporary failure",
        "service unavailable",
        "runner lost communication",
        "no space left on device",
    )
    _POLICY_MARKERS = (
        "permission denied",
        "resource not accessible by integration",
        "protected branch",
        "required approval",
        "secret is not available",
    )
    _CODE_MARKERS = (
        "assertionerror",
        "traceback",
        "syntaxerror",
        "typeerror",
        "test failed",
        "tests failed",
        "error:",
    )

    async def analyze(self, state: DeliveryState) -> CIFailureAnalysis:
        text = "\n".join(log.content for log in state.ci_logs).lower()
        evidence = tuple(
            f"{log.job_name}: {log.content[-1200:]}" for log in state.ci_logs
        )
        if any(marker in text for marker in self._POLICY_MARKERS):
            return CIFailureAnalysis(
                CIFailureKind.POLICY,
                "CI failed on policy or permission constraints.",
                evidence,
            )
        if any(marker in text for marker in self._INFRA_MARKERS):
            return CIFailureAnalysis(
                CIFailureKind.INFRASTRUCTURE,
                "CI failed on transient infrastructure symptoms.",
                evidence,
            )
        if any(marker in text for marker in self._CODE_MARKERS):
            return CIFailureAnalysis(
                CIFailureKind.CODE,
                "CI failed on code or test symptoms.",
                evidence,
            )
        return CIFailureAnalysis(
            CIFailureKind.UNKNOWN,
            "CI failure could not be classified safely.",
            evidence,
        )


class BoundedRemediationPolicy:
    def __init__(self, *, max_patch_attempts: int = 2, max_ci_retries: int = 1) -> None:
        if max_patch_attempts < 0 or max_ci_retries < 0:
            raise ValueError("remediation budgets must be non-negative")
        self.max_patch_attempts = max_patch_attempts
        self.max_ci_retries = max_ci_retries

    def decide(
        self,
        analysis: CIFailureAnalysis,
        history: tuple[RemediationRecord, ...],
    ) -> RemediationDecision:
        patch_count = sum(
            1 for item in history if item.action is RemediationAction.PATCH
        )
        retry_count = sum(
            1 for item in history if item.action is RemediationAction.RETRY_CI
        )
        if analysis.kind is CIFailureKind.CODE and patch_count < self.max_patch_attempts:
            return RemediationDecision(
                RemediationAction.PATCH,
                "code failure is inside autonomous patch budget",
            )
        if (
            analysis.kind is CIFailureKind.INFRASTRUCTURE
            and retry_count < self.max_ci_retries
        ):
            return RemediationDecision(
                RemediationAction.RETRY_CI,
                "transient CI failure is inside retry budget",
            )
        return RemediationDecision(
            RemediationAction.ESCALATE,
            f"no safe autonomous action remains for {analysis.kind.value}",
        )


class AutonomousDeliveryControlPlane:
    """Handle one terminal CI-failure event at a time.

    No hidden polling and no unbounded retries. The remediation ledger is
    durable and independent from Agent/runtime process lifetime, so restart
    cannot silently reset the attempt budget.
    """

    def __init__(
        self,
        *,
        ci: CIProvider,
        analyzer: CIFailureAnalyzer,
        remediator: RemediationExecutor,
        ledger: RemediationLedger,
        policy: BoundedRemediationPolicy | None = None,
    ) -> None:
        self._ci = ci
        self._analyzer = analyzer
        self._remediator = remediator
        self._ledger = ledger
        self._policy = policy or BoundedRemediationPolicy()

    async def handle_ci_failure(
        self,
        delivery_id: str,
        state: DeliveryState,
    ) -> DeliveryState:
        if state.phase is not DeliveryPhase.CI_FAILED:
            raise ValueError("CI remediation requires delivery.phase == CI_FAILED")
        if state.execution is None or state.ci_run is None:
            raise ValueError("CI remediation requires execution and ci_run")

        history = await self._ledger.list(delivery_id)
        analysis = await self._analyzer.analyze(state)
        decision = self._policy.decide(analysis, history)
        attempt = len(history) + 1

        if decision.action is RemediationAction.ESCALATE:
            await self._ledger.append(
                RemediationRecord(
                    delivery_id=delivery_id,
                    attempt=attempt,
                    failure_kind=analysis.kind,
                    action=decision.action,
                    outcome=RemediationOutcome.ESCALATED,
                    summary=decision.reason,
                    previous_commit_sha=state.execution.commit_sha,
                    evidence=analysis.evidence,
                )
            )
            return replace(
                state,
                phase=DeliveryPhase.REJECTED,
                verification=VerificationResult(
                    accepted=False,
                    summary=f"Human escalation required: {decision.reason}",
                    evidence=analysis.evidence,
                ),
            )

        if decision.action is RemediationAction.RETRY_CI:
            capabilities = await self._ci.capabilities()
            if CICapability.RETRY not in capabilities:
                reason = "CI provider does not support failed-run retry"
                await self._ledger.append(
                    RemediationRecord(
                        delivery_id=delivery_id,
                        attempt=attempt,
                        failure_kind=analysis.kind,
                        action=RemediationAction.ESCALATE,
                        outcome=RemediationOutcome.ESCALATED,
                        summary=reason,
                        previous_commit_sha=state.execution.commit_sha,
                        evidence=analysis.evidence,
                    )
                )
                return replace(
                    state,
                    phase=DeliveryPhase.REJECTED,
                    verification=VerificationResult(False, reason, analysis.evidence),
                )
            queued = await self._ci.retry_failed(state.ci_run)
            await self._ledger.append(
                RemediationRecord(
                    delivery_id=delivery_id,
                    attempt=attempt,
                    failure_kind=analysis.kind,
                    action=decision.action,
                    outcome=RemediationOutcome.COMPLETED,
                    summary=decision.reason,
                    previous_commit_sha=state.execution.commit_sha,
                    evidence=analysis.evidence,
                )
            )
            return replace(
                state,
                phase=DeliveryPhase.CI_PENDING,
                ci_run=queued,
                ci_logs=(),
                verification=None,
            )

        result = await self._remediator.remediate(
            state,
            analysis,
            attempt=attempt,
        )
        if not result.published:
            raise RuntimeError("RemediationExecutor must publish the repair commit")
        if result.source_branch != state.execution.source_branch:
            raise RuntimeError("Remediation must update the existing source branch")
        if result.commit_sha == state.execution.commit_sha:
            raise RuntimeError("Remediation must produce a new commit")

        await self._ledger.append(
            RemediationRecord(
                delivery_id=delivery_id,
                attempt=attempt,
                failure_kind=analysis.kind,
                action=decision.action,
                outcome=RemediationOutcome.COMPLETED,
                summary=decision.reason,
                previous_commit_sha=state.execution.commit_sha,
                resulting_commit_sha=result.commit_sha,
                evidence=analysis.evidence,
            )
        )
        return replace(
            state,
            phase=DeliveryPhase.CI_PENDING,
            execution=result,
            ci_run=None,
            ci_logs=(),
            verification=None,
        )
