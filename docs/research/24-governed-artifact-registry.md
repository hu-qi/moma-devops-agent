# 24 — Governed Artifact Registry and Rollback

Date: 2026-09-24  
Status: **Implemented and CI verified**

## Purpose

DevOpsPilot separates four different states that are often incorrectly collapsed into “self-evolution”:

1. candidate generation;
2. benchmark/regression approval;
3. human production approval;
4. active runtime version.

A candidate passing DevOpsBench does not automatically become active.

## Registry model

The SQLite control-plane registry stores:

- immutable artifact versions;
- staged candidate identity;
- one active-version pointer per artifact;
- append-only activation history.

It never writes directly to production Skill/Prompt files.

## Promotion rule

A candidate can become active only when all conditions are true:

- PromotionDecision belongs to the same candidate;
- state is APPROVED;
- automated EvolutionEvidence has gate_passed=true;
- a non-empty human decided_by identity is recorded.

PENDING_HUMAN and REJECTED decisions cannot activate an artifact.

## Rollback rule

Rollback is itself a governed human action.

For an updated artifact:

    active v2
      -> APPROVED rollback
      -> active v1

For a newly created artifact such as a Team Pattern / Swarm Skill:

    new artifact active
      -> APPROVED rollback target=None
      -> artifact deactivated

This matters because a newly created Team Pattern has no prior production version to restore.

## Separation from audit store

EvolutionAuditStore answers:

    What candidate/evidence/decision history happened?

ArtifactRegistry answers:

    Which immutable version is currently active?

Keeping these stores separate prevents an audit record from accidentally becoming a deployment mechanism.

## CI Evidence

Workflow:

    Evolution Artifact Registry

Verified:
- immutable version registration;
- staged candidate;
- PENDING_HUMAN promotion blocked;
- APPROVED + gate-passed promotion;
- rollback to prior version;
- deactivation rollback for newly created artifacts;
- activation history.
