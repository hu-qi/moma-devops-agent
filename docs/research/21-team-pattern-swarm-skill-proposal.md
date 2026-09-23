# 21 — Repeated Team Pattern to Governed Swarm Skill Proposal

Date: 2026-09-24
Status: **PROPOSAL STAGED / HUMAN APPROVAL REQUIRED**

## Evidence

Two independent task-correct AgentTeam executions exhibited the same runtime pattern:

1. DevOpsBench TaskExecutor
   - trajectory: df3bf8ab84422c053ad951c8e704b7f3
   - task_success: true
   - runtime_clean_completion: false
   - reason: agentteam_timeout

2. First live GitHub delivery
   - trajectory: df43e104d607bd752c1d8f8d13475da5
   - commit: fb2e70b74f16859afa5ee2f015ef9e8c864353fb
   - GitHub CI: success
   - task_success: true
   - runtime_clean_completion: false
   - reason: agentteam_timeout

## Opportunity Routing

DeliveryEvolutionMiner routes this pattern to:

    ArtifactKind.TEAM_PATTERN

It is deliberately not routed to build-debug Skill Experience or a single member harness.

## Existing Team Skill Check

Current DevOpsPilot skills root contains only:

    skills/build-debug/SKILL.md

There is no existing team-skill/swarm-skill to evolve.

Therefore TeamSkillEvolutionRail is not the correct first operation.

## OpenJiuwen Creation Boundary

DevOpsPilot uses OpenJiuwen TeamSkillCreateRail.propose_from_external_evidence().

OpenJiuwen requires:

- non-empty proposal key;
- reusable guidance;
- at least two deduplicated evidence items;
- caller-side semantic grouping;
- explicit approval before creation.

Run:

    Team Pattern Creation Proposal
    35930008850
    SUCCESS

Produced:

    proposal_id = team_skill_evolve_create_0a84bf96ac624bf0b30fd755417088c5
    proposal_key = devopspilot-team-runtime-agentteam-timeout
    evidence_count = 2
    production_write = false

OpenJiuwen emitted its canonical chat.ask_user_question approval event.

## Proposed Reusable Team Capability

Create a reusable DevOps delivery Team/Swarm Skill that defines Leader, Coding, and Review collaboration; explicit task dependency and completion criteria; bounded member shutdown/timeout handling; independent verification before delivery; and a deterministic handoff from member completion to Leader finalization.

## Persistence

SQLiteEvolutionAuditStore now persists TeamPatternCreationProposal as an immutable audit identity.

Evolution Audit Store run 35930115333: SUCCESS.

This prevents an in-memory Rail approval request from disappearing when a worker process exits.

## Creator Dependency Boundary

The official swarmskill-creator asset is maintained in:

    openJiuwen-ai/jiuwenswarm
    jiuwenswarm/resources/agent/workspace/skills/swarmskill-creator/

DevOpsPilot will treat it as an external creator dependency and will not vendor/copy it into this repository.

After explicit approval, the next implementation stage is:

    approved creation proposal
      -> sandbox swarmskill-creator
      -> Swarm Skill candidate
      -> validator
      -> DevOpsBench A/B
      -> RegressionGate
      -> human promotion decision

No production Skill is created at the proposal stage.