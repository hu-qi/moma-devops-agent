# 03 — MoMA × OpenJiuwen Integration Spike

Status: **Prepared; live execution requires MoMA credentials**

## Goal

Answer one question before implementing DevOpsPilot business logic:

> Can MoMA serve as the model layer for OpenJiuwen DeepAgent while preserving streaming, tool calling, usage telemetry and later AgentTeam execution?

## Spike Ladder

### S0 — Model Probe
MoMA → OpenJiuwen `Model.invoke()`.

Pass:
- returns assistant response
- model name / usage observable

### S1 — Streaming Probe
MoMA → OpenJiuwen `Model.stream()`.

Pass:
- chunks arrive incrementally
- finish reason is valid
- usage can be captured

### S2 — Tool Probe
MoMA model receives an OpenAI-format tool schema.

Pass:
- model returns tool call
- Jiuwen parses it correctly
- tool result can continue the turn

### S3 — DeepAgent Probe
`create_deep_agent(model=MoMA-backed Model)`.

Pass:
- ReAct turn completes
- tool invocation works
- workspace available

### S4 — AgentTeam Probe
Leader + Coding + Reviewer, all using model profiles backed by MoMA.

Pass:
- team builds
- tasks are delegated
- results return to Leader
- trace distinguishes member calls

### S5 — Evolution Probe
Execute repeated deterministic failure/success cases.

Pass:
- capture trajectory/evolution signal
- produce a candidate Skill/experience patch
- candidate is not silently promoted

## Environment

Never commit secrets.

```bash
export MOMA_API_BASE="..."
export MOMA_API_KEY="..."
export MOMA_MODEL="..."
```

Optional:
```bash
export MOMA_FAST_MODEL="..."
export MOMA_REASONING_MODEL="..."
export MOMA_CODING_MODEL="..."
export MOMA_REVIEW_MODEL="..."
```

## Current Result

- S0: PENDING CREDENTIAL
- S1: PENDING CREDENTIAL
- S2: PENDING CREDENTIAL
- S3: PENDING CREDENTIAL
- S4: PENDING CREDENTIAL
- S5: PENDING CREDENTIAL

Static compatibility assessment: **PASS / high confidence**.

## Rule

Do not mark a MoMA API feature as CONFIRMED merely because:
- MoMA platform marketing mentions it;
- another OpenAI-compatible service supports it;
- OpenJiuwen supports it.

Each MoMA request/response behavior must be recorded from a real call or official developer documentation.
