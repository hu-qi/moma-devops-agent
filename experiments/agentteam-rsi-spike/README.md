# AgentTeam + RSI Spike

This experiment validates the second layer of DevOpsPilot after basic MoMA → Model → DeepAgent compatibility.

## Confirmed runtime capabilities

OpenJiuwen currently exposes the AgentTeam and RSI primitives required by the product direction.

### AgentTeam
- TeamAgentSpec / DeepAgentSpec
- Leader + dynamic teammates
- inprocess / process execution
- memory / SQLite / PostgreSQL storage
- temporary / persistent lifecycle
- task verification
- HITT
- workspace isolation
- model pool / router support
- team-level evolution switch

### RSI
- AutoHarnessOrchestrator
- TeamEvaluator
- MemberOptimizer
- ProgramArtifactProvider
- SingleHarnessIterativeOptimizationOrchestrator
- evaluation / analysis primitives

## Live AgentTeam smoke

`agentteam_smoke.py` asks the Leader to dynamically create:
- Coding Analyst
- Reviewer

It does not modify a repository yet. The first goal is to prove the Team runtime and member collaboration path.

Required environment:

```text
MOMA_API_BASE
MOMA_API_KEY
MOMA_MODEL
```

## Why RSI is not run first

RSI needs an objective function.

DevOpsPilot will not claim a candidate is "better" based only on another model's opinion.

The first RSI target will be evaluated through DevOpsBench:

```text
build-debug Skill v1
        ↓
DevOpsBench CI fixtures
        ↓
OpenJiuwen RSI
        ↓
Candidate v2
        ↓
baseline vs candidate
        ↓
PromotionDecision
```

Therefore DevOpsBench v0.1 is the next dependency.
