# 02 — OpenJiuwen Runtime Research

Date: 2026-09-23  
Target: `openJiuwen-ai/agent-core` develop  
Observed package version: **openjiuwen 0.1.18**  
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
- Skill and team-skill evolution
- RSI / artifact optimization infrastructure

Recommendation remains:

> Use OpenJiuwen as runtime infrastructure, but keep DevOpsPilot contracts and domain policy outside OpenJiuwen internals.

## 2. Version / Stability

Current `pyproject.toml`:
- package: `openjiuwen`
- version: `0.1.18`
- Python: `>=3.11,<3.14`
- classifier: Beta

The repository default branch is currently `develop`.

Implication:
- do not track an unpinned moving branch in production;
- first PoC may follow current develop APIs;
- once the integration surface is validated, pin a package version or commit;
- isolate Jiuwen-specific code in adapters.

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

The runtime defines an `openai_compatible` endpoint profile.

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

DevOpsPilot should still own:
- Complexity Gate
- Team Pattern selection
- DevOps role definitions
- result verification
- metrics comparing single vs team execution

## 7. Self-Evolving / RSI

Current source contains two relevant layers.

### Skill / Team Skill Evolution
Documentation describes:
- trajectory-driven signals
- candidate experience
- user confirmation
- experience scoring
- simplify / rebuild / rollback
- Agent Skill evolution
- Swarm/Team Skill evolution

This aligns strongly with DevOpsPilot's safety boundary: evolution should propose and validate changes rather than silently rewrite production behavior.

### RSI / Harness RSI
Current source contains:
- `openjiuwen.rsi`
- `harness_rsi`
- evaluator
- artifact RSI
- program artifact optimization
- auto-harness related components

This is promising but more internal/research-oriented than the basic Skill evolution surface.

Decision:
- use stable Skill/Team evolution interfaces first;
- evaluate RSI internals as an `EvolutionProvider`;
- do not expose Jiuwen internal RSI object shapes as DevOpsPilot domain contracts.

## 8. Risks

### API churn
0.x + develop moves quickly.

Mitigation:
- pin version/commit
- adapter boundary
- contract tests

### Framework overreach
Jiuwen already provides routing/team/evolution concepts. DevOpsPilot must not become a thin configuration wrapper.

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
Do not put organization/repository/platform business state into Jiuwen session objects by default.

Keep DevOpsPilot domain state independently modelled.

## 9. Integration Verdict

| Area | Fit |
|---|---|
| MoMA-compatible model client | HIGH |
| DeepAgent | HIGH |
| Tools/MCP | HIGH |
| Dynamic AgentTeam | HIGH |
| Session/recovery | HIGH |
| Skill evolution | HIGH |
| RSI experimentation | MEDIUM-HIGH, validate APIs |
| Long-term API stability | MEDIUM |
| Need to fork runtime | NO |

**Decision: proceed.**
