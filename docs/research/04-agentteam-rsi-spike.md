# 04 — AgentTeam + RSI Spike

Date: 2026-09-23  
Status: **Started**

## 1. Why This Spike Exists

The question is no longer whether OpenJiuwen has AgentTeam and RSI.

Both capabilities are confirmed.

The questions are now:

1. Which OpenJiuwen objects should DevOpsPilot treat as stable integration surfaces?
2. Which objects must remain behind adapters because they are optimization/runtime internals?
3. How should DevOpsPilot combine AgentTeam execution and RSI without becoming a thin Jiuwen configuration wrapper?
4. What evidence must DevOpsBench collect before an evolved artifact is promoted?

## 2. Runtime Surface Gate

Before model-dependent tests, CI introspects the installed distribution and records:

- exact OpenJiuwen version
- `create_deep_agent`
- `Runner`
- `TeamAgentSpec`
- `DeepAgentSpec`
- `AutoHarnessOrchestrator`
- `create_auto_harness_orchestrator`
- `TeamEvaluator`
- `MemberOptimizer`
- `ProgramArtifactProvider`
- `SingleHarnessIterativeOptimizationOrchestrator`

This prevents assumptions based only on a moving source branch.

## 3. AgentTeam Spike

### AT-1 — Static Team

Goal:
Leader + Coding + Reviewer can execute one deterministic task.

Expected flow:

```text
Leader
  ↓
Coding
  ↓
Patch + Tests
  ↓
Reviewer
  ↓
Verification
```

Measure:
- model calls per member
- tool calls
- latency
- task result
- review findings
- context duplication

### AT-2 — Dynamic Team Decision

Goal:
DevOpsPilot Complexity Gate decides between:

```text
single-agent
vs
dynamic AgentTeam
```

OpenJiuwen must execute the selected topology, but **DevOpsPilot owns the decision**.

### AT-3 — Workspace Isolation

Verify:
- same repository context is visible to members;
- coding member can modify workspace;
- reviewer can inspect independently;
- parallel members cannot silently corrupt the same worktree;
- team result records member attribution.

### AT-4 — Recovery

Verify:
- session persistence
- warm recovery
- process restart / cold recovery
- task state after failure

## 4. RSI Spike

### RSI-1 — Evaluation Surface

Map DevOpsBench cases into the minimum structures required by OpenJiuwen evaluator / optimizer components.

### RSI-2 — Single Harness Optimization

Candidate target:
`build-debug` Skill / prompt strategy.

Input:
- deterministic CI failure fixtures
- baseline Skill
- benchmark scoring

Output:
- candidate artifact
- score delta
- trace
- cost

### RSI-3 — Member Optimization

Candidate:
Coding or CI Specialist strategy.

DevOpsPilot must capture the candidate as its own `EvolutionArtifact`, not leak Jiuwen internal state into product domain objects.

### RSI-4 — Team Pattern Optimization

Later spike:
optimize collaboration pattern, e.g.

```text
Leader → Coding → Review
```

versus

```text
Leader
  ├─ Coding
  └─ Reviewer (early parallel inspection)
       ↓
Leader Verify
```

Promotion requires DevOpsBench evidence.

## 5. Proposed Adapter Boundary

```text
DevOpsPilot
│
├─ TeamExecutionProvider
│    └─ OpenJiuwenAgentTeamProvider
│
└─ EvolutionProvider
     ├─ OpenJiuwenOnlineEvolutionProvider
     └─ OpenJiuwenRSIProvider
```

### DevOpsPilot Contracts

```text
TeamPattern
TeamRunRequest
TeamRunResult

Trajectory
EvolutionRequest
EvolutionArtifact
EvaluationResult
PromotionDecision
```

### OpenJiuwen Objects

Stay inside adapters:
- TeamAgentSpec
- DeepAgentSpec
- TeamEvaluator
- MemberOptimizer
- AutoHarnessOrchestrator
- ProgramArtifactProvider
- internal RSI schemas

## 6. Critical Product Rule

RSI is an **optimizer**, not the product authority.

```text
RSI produces Candidate
        ↓
DevOpsBench evaluates Candidate
        ↓
Policy / Regression Gate
        ↓
Human Approval
        ↓
Artifact Registry promotes version
```

OpenJiuwen may optimize; DevOpsPilot decides whether the result is allowed to become a product capability.

## 7. Exit Criteria

This spike is complete when we can demonstrate:

- installed runtime surface captured in CI;
- one AgentTeam task runs end-to-end;
- one deterministic RSI/evolution candidate is generated;
- DevOpsBench can compare baseline vs candidate;
- candidate can be rejected without mutating the active production artifact.
