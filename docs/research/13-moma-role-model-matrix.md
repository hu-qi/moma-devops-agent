# 13 — MoMA AgentTeam Role Model Matrix

Date: 2026-09-24  
Status: **Live capability evidence integrated into runtime routing**

## Why Some Actions Were Red

The red runs did not indicate that MoMA itself was unavailable.

Two candidate models passed basic chat but failed the structured Tool Calling requirement used by OpenJiuwen AgentTeam:

| Model | Basic Chat | Structured tool_calls | AgentTeam tool-role |
|---|---:|---:|---:|
| GLM-5.3 | PASS | PASS | ELIGIBLE |
| Qwen3-32B | PASS | PASS | ELIGIBLE |
| deepseek-v4.1-flash | PASS | PASS | ELIGIBLE |
| DeepSeek-R1-0528 | PASS | FAIL | INELIGIBLE |
| qwen2.5-coder-32b-Instruct | PASS | FAIL | INELIGIBLE |

Observed behavior:

- `DeepSeek-R1-0528` returned reasoning plus a textual pseudo function call, but `tool_calls=[]` and `finish_reason=stop`.
- `qwen2.5-coder-32b-Instruct` returned a JSON text describing the desired function invocation, but not an OpenAI structured `tool_calls` object.
- The three eligible models returned real structured tool calls through the same MoMA OpenAI-compatible endpoint.

## Provisional Role Defaults

These are capability-qualified defaults, not benchmark winners:

```text
Leader / Reasoning -> GLM-5.3
Coding             -> Qwen3-32B
Review             -> deepseek-v4.1-flash
```

The next selection layer is DevOpsBench:
- task success;
- first-pass test/CI success;
- latency;
- token usage;
- cost;
- review quality.

## Runtime Guard

Capability evidence now enters `RoutingDecision.verified_features`.

Tool-using AgentTeam roles require:

```text
ModelRuntimeFeature.STRUCTURED_TOOL_CALLING
```

Unknown or known-ineligible models are rejected before AgentTeam execution. This prevents a conversation-capable model from being mistaken for an autonomous tool-using Agent model.

## Action Noise

`MoMA Role Model Matrix` now treats unsupported candidate models as research evidence rather than workflow failures.

A separate strict job validates only the models currently selected for production-like AgentTeam roles.

`OpenJiuwen Task Executor` keeps `cancel-in-progress: true`; cancelled runs during rapid repository updates are expected superseded executions, not MoMA failures.
