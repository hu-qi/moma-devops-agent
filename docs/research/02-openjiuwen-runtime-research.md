# 02 — OpenJiuwen Runtime Research

Date: 2026-09-23  
Target: `openJiuwen-ai/agent-core` / official openJiuwen distribution  
Status: **Static API/source validation completed; live MoMA integration pending**

## 1. Executive Conclusion

OpenJiuwen Agent Core is a strong fit for DevOpsPilot as an SDK / Runtime dependency.

Current source and documentation confirm the presence of the key primitives needed by the product:
- OpenAI-compatible model endpoints
- Tool Calling
- Streaming
- DeepAgent
- Skills
- MCP
- Workspace
- Sub-agents
- Task loop / planning
- AgentTeam
- Persistent session / recovery
- Permissions / HITL
- Trajectory / observability
- Skill and Team/Swarm Skill evolution
- **RSI / Recursive Self-Improvement**
- Harness optimization / artifact optimization infrastructure

Recommendation:

> Use OpenJiuwen as runtime infrastructure, but keep DevOpsPilot contracts, DevOps policy, evaluation and promotion gates outside OpenJiuwen internals.

## 2. Version / Distribution Baseline

As of 2026-09-23, the public PyPI package and the GitHub `develop` mirror that can be independently verified expose `openjiuwen 0.1.18`.

A newer `0.1.19` baseline may exist in another release channel / upstream state, but it has not yet been independently verified from the public GitHub mirror or PyPI during this research pass.

Therefore DevOpsPilot does **not** hard-code the version in architecture documents.

For experiments:
- use a configurable `OPENJIUWEN_INSTALL_SPEC`;
- pin the exact package/tag/commit once the target 0.1.19 source is verified;
- keep Jiuwen-specific integration behind adapters and contract tests.

Python support in the currently verified public package:
- Python `>=3.11,<3.14`
- Development Status: Beta

## 3. LLM Integration

`ModelClientConfig` explicitly supports:
- `client_provider`
- `api_base`
- `api_key`
- custom headers
- timeout / retry
- API mode
- auth mode
- `endpoint_profile`
- request extensions

The runtime defines a generic `openai_compatible` endpoint profile.

This is important for MoMA because a generic OpenAI-compatible endpoint can be represented without implementing a custom Jiuwen model client.

Recommended initial configuration:

```python
ModelClientConfig(
    client_provider="OpenAI",
    api_base=MOMA_API_BASE,
    api_key=MOMA_API_KEY,
    endpoint_profile="openai_compatible",
)
```

## 4. Model Features Confirmed in Jiuwen

The common Model API supports:
- async `invoke`
- async `stream`
- JSON-schema-like tool definitions
- tool calls in assistant responses
- usage metadata
- reasoning content in streaming where supported
- custom request headers

Whether each feature works through MoMA depends on MoMA/model compatibility and must be tested separately.

## 5. DeepAgent Surface

Current `create_deep_agent(...)` public factory supports:
- model
- system prompt
- tools
- MCP servers
- subagents
- rails
- task loop
- async subagent
- workspace
- skills
- task planning
- permissions/config kwargs

This maps well to DevOpsPilot:

| DevOpsPilot | OpenJiuwen primitive |
|---|---|
| DevOps Leader | DeepAgent |
| Coding/Review/CI Specialist | DeepAgent / Team member |
| Skill | Skills / Skill rails |
| Git/CI/SCM actions | Tools / MCP |
| Repo sandbox | Workspace / SysOperation |
| Planner | Task planning / custom orchestration |
| Long task lifecycle | Task loop |
| Guardrails | Permissions / custom Rails |
| Trace | Observability / trajectory rails |

## 6. AgentTeam

Current AgentTeams support:
- Leader + Teammates
- in-process or process member execution
- persistent or temporary lifecycle
- SQLite / PostgreSQL / memory storage
- streaming execution
- interaction while running
- checkpoint/recovery
- member health checking / restart
- dynamic member spawning in current source

This supports the V1 design:

```text
Simple task → Leader / single DeepAgent

Complex task → Leader
                ├─ Coding
                ├─ Review
                └─ CI
```

DevOpsPilot still owns:
- Complexity Gate
- Team Pattern selection
- DevOps role definitions
- result verification
- metrics comparing single vs team execution

## 7. RSI — Confirmed Capability

RSI is no longer treated as a speculative capability.

The current public `openjiuwen.rsi` surface exports, among others:
- `AutoHarnessOrchestrator`
- `create_auto_harness_orchestrator`
- `TeamEvaluator`
- `MemberOptimizer`
- `ProgramArtifactProvider`
- `PaperArtifactProvider`
- `SingleHarnessIterativeOptimizationOrchestrator`
- `EvaluationResultAnalyzer`
- `DataLoader`
- optimization task / stage / dataset contracts

This confirms that openJiuwen already provides a real Recursive Self-Improvement / Harness optimization substrate.

### Two Evolution Layers

#### A. Online Skill / Team Skill Evolution

Best suited for production learning:
- trajectory-driven signals
- candidate experience
- user confirmation
- experience scoring
- simplify / rebuild / rollback
- member-level and team-level learning

#### B. RSI / Harness Optimization

Best suited for controlled offline / benchmark-driven optimization:
- evaluator
- member optimizer
- artifact/program optimization
- iterative harness optimization
- auto-harness orchestration

## 8. DevOpsPilot Evolution Mapping

Recommended design:

```text
DevOpsPilot Evolution Engine
          │
          ├─ Online Experience Provider
          │      └─ OpenJiuwen Skill / Team Skill Evolution
          │
          └─ RSI Provider
                 └─ OpenJiuwen RSI / Harness RSI
```

DevOpsPilot-owned contracts remain:
- `Trajectory`
- `EvolutionArtifact`
- `EvaluationResult`
- `PromotionDecision`
- `RollbackTarget`

OpenJiuwen-owned objects must stay behind the provider adapter.

## 9. Evolution Policy

Production path:

```text
Real Task
  ↓
Trajectory
  ↓
Online Evolution Signal
  ↓
Candidate Experience / Skill Change
  ↓
Human confirmation
```

Offline RSI path:

```text
DevOpsBench
  ↓
RSI Optimizer
  ↓
Candidate Prompt / Skill / Team Pattern / Harness Strategy
  ↓
Benchmark + Regression Gate
  ↓
Human Approval
  ↓
Promotion
```

This creates a safer division:
- online evolution captures experience;
- RSI searches for better strategies;
- DevOpsBench decides whether a candidate is actually better.

## 10. Risks

### API churn
0.x APIs can change rapidly.

Mitigation:
- configurable install spec
- pin exact version/commit for milestone builds
- adapter boundary
- contract tests

### Framework overreach
Jiuwen already provides team/evolution concepts. DevOpsPilot must not become a thin configuration wrapper.

DevOpsPilot-owned assets remain:
- DevOps TaskProfiler
- RoutingPolicy
- Team Patterns
- SCM / CI Providers
- DevOps Skills
- Industry Packs
- DevOpsBench
- Evolution policy and promotion gates

### Runtime vs product state
Organization/repository/platform business state should not be implicitly owned by Jiuwen session objects.

Keep DevOpsPilot domain state independently modelled.

## 11. Integration Verdict

| Area | Fit |
|---|---|
| MoMA-compatible model client | HIGH |
| DeepAgent | HIGH |
| Tools/MCP | HIGH |
| Dynamic AgentTeam | HIGH |
| Session/recovery | HIGH |
| Skill evolution | HIGH |
| RSI / Harness optimization | HIGH, API adapter still required |
| Long-term API stability | MEDIUM |
| Need to fork runtime | NO |

**Decision: proceed with OpenJiuwen as the core SDK / Runtime dependency and RSI provider candidate.**
