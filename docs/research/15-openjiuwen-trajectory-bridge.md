# 15 — OpenJiuwen Trajectory Bridge

Date: 2026-09-24  
Status: **Integration design confirmed from OpenJiuwen 0.1.19 source**

## Finding

OpenJiuwen already exposes a canonical observability path suitable for DevOpsPilot.

Relevant public/runtime primitives:

- `TrajectorySpanProcessor`
- `get_trajectory_span_processor()`
- `TrajectoryRail`
- `FileTrajectoryStore` / `InMemoryTrajectoryStore`
- OpenTelemetry GenAI semantic conventions
- AgentTeam-specific span attributes

The RSI / Skill Evolution implementation consumes the same trajectory
infrastructure, so DevOpsPilot should bridge this data rather than parse console
logs.

## Important Standard Attributes

LLM:
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`
- model/provider identifiers
- prompts/completions
- structured tool calls

OpenJiuwen extensions:
- total latency
- TPOT
- reasoning duration
- provider metadata

AgentTeam:
- team/member identity
- task identity/status/assignee
- member lifecycle/restart
- message and review flow

## Mapping

```text
OpenJiuwen OTEL / canonical trajectory
                 ↓
      OpenJiuwenTrajectoryBridge
                 ↓
DevOpsPilot DeliveryTrajectory
                 ↓
       ┌─────────┴─────────┐
       ↓                   ↓
 DevOpsBench            RSI / Evolution
 metrics                candidate mining
```

DevOpsPilot remains owner of its domain trajectory schema. OpenJiuwen remains
the runtime source of execution spans.

## Mapping Rules

### Model call

OpenJiuwen LLM span:

```text
model/provider
input/output tokens
latency
reasoning
```

becomes:

```text
TrajectoryEventKind.ROUTING
name = model.invoke
```

### Tool call

OpenJiuwen tool span becomes:

```text
TrajectoryEventKind.TOOL
name = <tool name>
status = success/error
```

### Agent / team

Member lifecycle and task spans become:

```text
TrajectoryEventKind.AGENT
```

with role/member/task metadata.

### Business-side events

SCM / CI / human approval remain recorded by DevOpsPilot itself rather than
being inferred from runtime spans.

## Why Not Parse Action Logs

Console logs are:
- presentation-oriented;
- noisy;
- unstable across formatter changes;
- may include expected capability-probe errors;
- not guaranteed to preserve parent/child structure.

Canonical spans are structured and are also the data substrate used by
OpenJiuwen evolution.

## Next Implementation

1. Acquire team observability before AgentTeam execution.
2. Share the process-wide `TrajectorySpanProcessor`.
3. Capture the execution by the same stable session id used by DevOpsPilot.
4. Convert LLM/tool/member/task spans into `DeliveryTrajectory`.
5. Add the resulting trajectory id and usage totals to `ExecutionResult.metadata`.
6. Feed the canonical trajectory directly into
   `trajectory_runtime_metrics()` and later RSI candidate generation.

This bridge should be implemented after the heterogeneous role-model baseline
is stable, so observability changes do not obscure runtime/model debugging.
