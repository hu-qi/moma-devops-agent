"""Mine governed evolution opportunities from delivery outcomes."""

from __future__ import annotations

from devopspilot.contracts.delivery import DeliveryPhase, DeliveryState
from devopspilot.contracts.evolution import (
    ArtifactKind,
    EvolutionOpportunity,
    EvolutionSignalEvidence,
    OpportunityPriority,
)


class DeliveryEvolutionMiner:
    """Classify delivery evidence before invoking any evolution provider."""

    def mine(self, state: DeliveryState) -> tuple[EvolutionOpportunity, ...]:
        execution = state.execution
        if execution is None:
            return ()

        trajectory_id = execution.metadata.get("trajectory_id", "").strip() or None
        source_ids = (trajectory_id,) if trajectory_id else ()
        opportunities: list[EvolutionOpportunity] = []

        runtime_degraded = (
            execution.metadata.get("runtime_degraded", "").lower() == "true"
        )
        runtime_reason = execution.metadata.get(
            "runtime_degradation_reason", ""
        ).strip()

        if runtime_degraded:
            reason = runtime_reason or "runtime-degraded"
            signal = EvolutionSignalEvidence(
                signal_type="runtime_degradation",
                section="AgentTeam Runtime",
                excerpt=(
                    "The software task passed independent engineering gates, "
                    f"but the AgentTeam runtime degraded: {reason}."
                ),
                source="delivery",
                trajectory_id=trajectory_id,
                metadata={
                    "task_success": str(
                        state.phase
                        in {DeliveryPhase.CI_PASSED, DeliveryPhase.VERIFIED}
                    ).lower(),
                    "runtime_clean_completion": "false",
                    "runtime_degradation_reason": reason,
                },
            )
            opportunities.append(EvolutionOpportunity(
                opportunity_id=(
                    f"team-pattern:{state.task.work_item.item_id}:{reason}"
                ),
                target_kind=ArtifactKind.TEAM_PATTERN,
                objective=(
                    "Improve AgentTeam completion and termination behavior "
                    "without reducing task correctness, tool safety, review "
                    "independence, or deterministic verification."
                ),
                source_trajectory_ids=source_ids,
                signals=(signal,),
                priority=OpportunityPriority.HIGH,
                auto_candidate_allowed=True,
                metadata={
                    "work_item_id": state.task.work_item.item_id,
                    "repository": state.task.repository.full_name,
                },
            ))

        if state.phase is DeliveryPhase.CI_FAILED:
            excerpt = "\n".join(
                log.content[-1200:] for log in state.ci_logs[:3]
            ).strip()
            signal = EvolutionSignalEvidence(
                signal_type="ci_failure",
                section="Build Debug",
                excerpt=excerpt or "CI failed without retrievable logs.",
                source="delivery",
                trajectory_id=trajectory_id,
                tool_name="ci-log",
                metadata={
                    "ci_run_id": state.ci_run.run_id if state.ci_run else "",
                    "ci_conclusion": (
                        state.ci_run.conclusion if state.ci_run else ""
                    ),
                },
            )
            opportunities.append(EvolutionOpportunity(
                opportunity_id=(
                    f"build-debug:{state.task.work_item.item_id}:ci-failure"
                ),
                target_kind=ArtifactKind.SKILL_EXPERIENCE,
                objective=(
                    "Improve build-debug diagnosis using the observed CI "
                    "failure while preserving repository and path constraints."
                ),
                source_trajectory_ids=source_ids,
                signals=(signal,),
                priority=OpportunityPriority.HIGH,
                auto_candidate_allowed=True,
                metadata={"skill_name": "build-debug"},
            ))

        if (
            state.phase is DeliveryPhase.VERIFIED
            and not runtime_degraded
            and execution.metadata.get("tool_calls")
        ):
            signal = EvolutionSignalEvidence(
                signal_type="successful_delivery",
                section="Tool Strategy",
                excerpt=(
                    "The delivery completed cleanly. Preserve or simplify the "
                    "successful tool sequence only if DevOpsBench confirms no "
                    "regression."
                ),
                source="delivery",
                trajectory_id=trajectory_id,
                metadata={
                    "tool_calls": execution.metadata.get("tool_calls", "0"),
                    "model_calls": execution.metadata.get("model_calls", "0"),
                },
            )
            opportunities.append(EvolutionOpportunity(
                opportunity_id=(
                    f"tool-strategy:{state.task.work_item.item_id}:success"
                ),
                target_kind=ArtifactKind.TOOL_STRATEGY,
                objective=(
                    "Explore whether the successful delivery tool sequence can "
                    "be simplified without reducing quality or safety."
                ),
                source_trajectory_ids=source_ids,
                signals=(signal,),
                priority=OpportunityPriority.LOW,
                auto_candidate_allowed=True,
            ))

        return tuple(opportunities)
