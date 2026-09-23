# 20 — Delivery Evidence to Evolution Opportunity Routing

Date: 2026-09-24
Status: **Implemented**

## Purpose

Do not send every trajectory to the same self-evolution mechanism.

DevOpsPilot first classifies what actually needs to improve:

    delivery evidence
       ↓
    DeliveryEvolutionMiner
       ↓
    EvolutionOpportunity
       ├─ TEAM_PATTERN
       ├─ SKILL_EXPERIENCE
       └─ TOOL_STRATEGY

## Current Rules

### Task correct, runtime degraded

Example: first live GitHub E2E.

    task_success = true
    runtime_clean_completion = false
    reason = agentteam_timeout

Target:

    TEAM_PATTERN

Rationale: the software-engineering result is correct; the problem is team lifecycle/termination behavior. Changing build-debug or coding Skills would be the wrong intervention.

### CI failure with logs

Target:

    SKILL_EXPERIENCE(build-debug)

Rationale: CI diagnosis evidence can improve reusable debugging experience.

### Clean verified success

Target:

    TOOL_STRATEGY

Priority is low. Successful traces may be mined for simplification/cost reduction, but only if DevOpsBench proves no regression.

## Safety

An EvolutionOpportunity is not a production mutation.

Flow remains:

    Opportunity
      -> Candidate generation
      -> Sandbox
      -> DevOpsBench
      -> RegressionGate
      -> Human Approval
      -> Versioned Promotion

## Next

Implement a TEAM_PATTERN candidate provider backed by OpenJiuwen RSI/AutoHarness for the live AgentTeam timeout opportunity.