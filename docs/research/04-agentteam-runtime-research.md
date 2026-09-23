# 04 — OpenJiuwen AgentTeam Runtime Research

Date: 2026-09-23  
Status: **Static source/API validation complete**

## Executive Conclusion

OpenJiuwen AgentTeams already contains most of the generic runtime machinery DevOpsPilot needs. DevOpsPilot should **not** build a second multi-agent scheduler.

The product-owned layer should focus on:
- Complexity Gate
- DevOps Team Pattern
- specialist role contracts
- scheduling policy
- verification policy
- model capability assignment
- metrics and evaluation

## Confirmed Runtime Capabilities

Current `TeamAgentSpec` exposes:

- Leader + teammate DeepAgent specs
- temporary / persistent lifecycle
- dynamic and predefined team modes
- dynamic `spawn_member`
- autonomous or scheduled dispatch
- team-level task verification
- configurable review rounds
- member workspace isolation
- worktree support
- in-process / process spawn
- in-process / pyzmq / hybrid transport
- SQLite / PostgreSQL / MySQL / memory storage
- HITT capability
- reliability controls
- shared model pool
- model router
- IntelliRouter / failover routing
- team self-evolution switch
- team planning
- team memory/workspace configuration

## Important Finding: TeamAgentSpec Already Has Evolution

`TeamAgentSpec.evolution_enabled` is a first-class field and defaults to true in current develop source.

This strengthens the decision to treat OpenJiuwen as the runtime and evolution substrate while keeping DevOpsPilot's evolution policy independent.

## Recommended DevOpsPilot V1 Mapping

### Leader
Use a fixed DevOps Leader.

Responsibilities owned by DevOpsPilot:
- create TaskProfile
- run Complexity Gate
- select Team Pattern
- select model capability profile
- final delivery verification

### Dynamic Members
Initial roles:
- Coding
- Reviewer
- CI Debugger

Do not create permanent agents for every Skill.

## Recommended Team Mode

For the first auditable DevOps implementation:

```text
team_mode = hybrid/default
dispatch_mode = scheduled
enable_task_verification = true
spawn_mode = inprocess
```

Rationale:
- dynamic specialists remain possible;
- scheduled dispatch is easier to explain and evaluate;
- explicit reviewer assignment maps to DevOps quality gates;
- in-process reduces infrastructure variables during the first PoC.

Later:
- process isolation for untrusted/high-cost tasks;
- pyzmq for distributed execution;
- persistent lifecycle for long-running project teams.

## Workspace Strategy

Coding tasks should not share an uncontrolled writable workspace.

Preferred evolution:

```text
V1: isolated workspace
 ↓
V1.1: git worktree per coding task/member
 ↓
V2: sandbox/container execution
```

Reviewer should normally inspect the produced diff read-only.

## Model Allocation

OpenJiuwen TeamAgentSpec already supports:
- `model_pool`
- `model_router`
- `model_intelli_router`

DevOpsPilot should **not directly expose these as product contracts**.

Instead:

```text
TaskProfile
 ↓
DevOpsPilot RoutingDecision
 ↓
ModelCapabilityProfile
 ↓
MoMAProvider
 ↓
OpenJiuwen team/member model config
```

This preserves MaaS portability.

## Runtime Features We Intentionally Reuse

- member lifecycle
- messaging
- task board
- persistence/recovery
- workspace plumbing
- review dispatch primitives
- HITT plumbing
- reliability rail
- transport/storage

## Runtime Features We Intentionally Own

- when to form a team
- which DevOps roles are required
- role capabilities
- risk-based approval
- what counts as completion
- what counts as a valid code review
- CI/pass/fail verification
- benchmark metrics

## Next Live Spike

Build a minimal team:

```text
Leader
 ├─ Coding Agent
 └─ Review Agent
```

Task:
- Coding returns a structured patch proposal.
- Reviewer independently checks it.
- Leader returns a structured verification result.

No SCM mutation in the first team spike.
