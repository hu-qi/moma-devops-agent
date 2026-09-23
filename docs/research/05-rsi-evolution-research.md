# 05 — OpenJiuwen RSI / Self-Evolution Research

Date: 2026-09-23  
Status: **Capability confirmed; integration boundary defined**

## Executive Conclusion

Current OpenJiuwen source has genuine RSI/self-evolution capabilities; it is not merely prompt optimization.

Confirmed code surfaces include:
- `openjiuwen.rsi`
- Artifact RSI
- Harness RSI
- Auto Harness
- evaluator / case runner
- dataset loading
- member optimizer
- program artifact optimization
- RSI event/schema/usage contracts
- skill evolution rails
- team-skill evolution rails

DevOpsPilot should use these capabilities, but not expose OpenJiuwen internal schemas as its product data model.

## Two Evolution Layers

### Layer A — Online Operational Evolution

Use OpenJiuwen Skill / Team Skill evolution for:
- execution experience
- troubleshooting patterns
- user correction
- team collaboration patterns
- reusable operating constraints

Flow:

```text
Task trajectory
  ↓
Evolvable signal
  ↓
Candidate experience
  ↓
Human confirmation
  ↓
Experience store
  ↓
Future task reuse
```

This is suitable for fast, bounded learning.

### Layer B — Offline Governed RSI

Use `openjiuwen.rsi` / Harness RSI for deeper optimization:
- harness strategy
- artifact candidate generation
- member/team optimization
- evaluation-driven search
- candidate comparison

Flow:

```text
Trajectory dataset
  ↓
Optimization hypothesis
  ↓
Candidate artifact
  ↓
DevOpsBench
  ↓
Regression Gate
  ↓
Human approval
  ↓
Versioned promotion
```

This is the preferred path for competition-grade “self-evolving” evidence.

## DevOpsPilot Evolution Contract

DevOpsPilot owns a stable domain abstraction:

```text
EvolutionRequest
EvolutionCandidate
EvolutionEvidence
PromotionDecision
ArtifactVersion
```

Provider mapping:

```text
EvolutionEngine
   ↓
EvolutionProvider
   ├─ OpenJiuwenSkillEvolutionProvider
   └─ OpenJiuwenRsiProvider
```

## What Can Evolve in V1

Allowed:
- Skill
- Prompt
- Routing Policy
- Team Pattern
- Tool Strategy

Not automatically promoted:
- Runtime code
- credential/permission policy
- production deploy policy
- compliance baseline
- industry regulation source

## Critical Governance Rule

RSI success is not “the model changed itself”.

A candidate is only better if:
- it passes deterministic tests;
- it improves target benchmark metrics;
- it causes no critical regression;
- provenance is preserved;
- it is versioned and reversible.

## Why DevOpsBench Is Mandatory

Without a benchmark, RSI becomes an unverifiable narrative.

DevOpsPilot therefore treats:

```text
RSI + DevOpsBench + Promotion Gate
```

as one product capability, not three unrelated features.

## Initial RSI Demonstration Target

Recommended first artifact: `build-debug` Skill.

Reason:
- failures are deterministic;
- logs provide strong trajectories;
- success can be measured by CI recovery;
- skill improvements are easy to explain.

Example:

```text
build-debug v1
  ↓
repeated dependency-resolution failures
  ↓
candidate adds pre-check + log triage ordering
  ↓
DevOpsBench CI-debug cases
  ↓
higher success / fewer tool calls
  ↓
candidate ready for approval
```

## Version Note

The public GitHub Release and PyPI observed on 2026-09-23 still expose 0.1.18, while current develop contains the RSI surfaces above.

DevOpsPilot will target the newest validated OpenJiuwen distribution available to the team (expected 0.1.19) but keep the runtime adapter pinned and replaceable.
