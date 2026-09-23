# 15 — MoMA Model Capability vs OpenJiuwen AgentTeam Runtime

Date: 2026-09-24  
Status: **Failure modes separated by live CI evidence**

## Executive Conclusion

Recent red GitHub Actions do **not** have a single root cause.

There are two distinct classes:

### A. Model capability mismatch

Some MoMA-hosted models support normal chat but do not emit standard OpenAI `tool_calls`.

Observed:

| Model | Basic chat | Structured tool_calls | Tool-using AgentTeam |
|---|---:|---:|---:|
| GLM-5.3 | PASS | PASS | ELIGIBLE |
| Qwen3-32B | PASS | PASS | ELIGIBLE |
| deepseek-v4.1-flash | PASS | PASS | ELIGIBLE |
| DeepSeek-R1-0528 | PASS | FAIL | INELIGIBLE |
| qwen2.5-coder-32b-Instruct | PASS | FAIL | INELIGIBLE |

This is a **per-model protocol capability issue**, not a general MoMA outage.

### B. AgentTeam lifecycle / termination instability

The latest live TaskExecutor runs show a different failure:

- Coding Agent successfully modified the target file.
- Real Git diff was produced.
- Tests were executed successfully.
- Coding Agent sent patch/test evidence.
- Review Agent was dynamically spawned.
- Review Agent received an independent verification task.
- OpenJiuwen emitted member-state transition errors such as `idle -> running`, `idle -> completing`, and `idle -> completed`.
- The Team stream remained open until the DevOpsPilot execution timeout.
- The final exception was `OpenJiuwen AgentTeam exceeded delivery execution timeout`.

This is primarily a **runtime completion/lifecycle problem**, not evidence that the selected MoMA models failed to reason or call tools.

## Runtime Policy

DevOpsPilot must not equate clean Team stream termination with software-delivery success, and must not equate a Team stream timeout with software-delivery failure.

Software-delivery success is determined by independent product gates:

1. expected code diff exists;
2. forbidden paths are untouched;
3. changed-file budget is respected;
4. independent repository tests pass;
5. DevOpsBench oracle passes;
6. canonical trajectory is captured;
7. runtime degradation is recorded separately.

## Degraded Runtime Handling

Current executor policy:

    AgentTeam stream timeout
            ↓
    record runtime_degraded=true
            ↓
    stop OpenJiuwen Runner
            ↓
    drain trajectory
            ↓
    independent file/test constraints
            ↓
    DevOpsBench oracle
            ↓
    only then accept/reject delivery result

This does not hide framework instability. It separates **task correctness** from **runtime health**.

## Metrics Implication

DevOpsBench should eventually report both `task_success` and `runtime_clean_completion`.

A candidate architecture can therefore be task-correct but runtime-degraded, runtime-clean but task-wrong, both correct, or neither.

## Current Role Defaults

Capability-qualified, not benchmark-winning:

    Leader / Reasoning -> GLM-5.3
    Coding             -> Qwen3-32B
    Review             -> deepseek-v4.1-flash

Quality selection still belongs to DevOpsBench/ablation, not to protocol compatibility alone.

## Next

1. Confirm the degraded-runtime executor can still pass deterministic DevOpsBench gates.
2. Add `runtime_clean_completion` to benchmark/evaluation metrics.
3. Open an upstream OpenJiuwen issue or minimal reproducer for Team state-transition/stream-termination behavior if it remains reproducible.
4. Keep unsupported tool-call models available for non-tool roles rather than globally rejecting them.