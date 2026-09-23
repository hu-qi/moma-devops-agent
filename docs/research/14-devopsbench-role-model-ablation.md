# 14 — DevOpsBench Role-Model Ablation Plan

Date: 2026-09-24  
Status: **Prepared after MoMA capability gating**

## Goal

Move model-role selection from intuition to evidence.

Only models that already satisfy the current AgentTeam runtime contract are eligible:

- `GLM-5.3`
- `Qwen3-32B`
- `deepseek-v4.1-flash`

The following models are excluded from tool-using AgentTeam role experiments until their MoMA/OpenAI-compatible structured Tool Calling behavior changes:

- `DeepSeek-R1-0528`
- `qwen2.5-coder-32b-Instruct`

## Current Capability-Qualified Baseline

```text
Leader / Reasoning -> GLM-5.3
Coding             -> Qwen3-32B
Review             -> deepseek-v4.1-flash
```

This is a bootstrap assignment, not an overall ranking.

## Experiment Design

Do not test all 3^3 combinations initially.

Use controlled one-factor-at-a-time ablation.

### E1 — Coding role

Hold:

```text
Leader = GLM-5.3
Review = deepseek-v4.1-flash
```

Compare:

```text
Coding = Qwen3-32B
Coding = deepseek-v4.1-flash
Coding = GLM-5.3
```

Run against coding + CI-debug cases.

### E2 — Leader role

Select the best stable Coding configuration from E1.

Hold Review fixed.

Compare the remaining eligible models as Leader.

Measure planning/tool-loop quality in addition to end-task success.

### E3 — Review role

Hold the selected Leader + Coding configuration.

Compare reviewer models on:
- seeded review defects;
- deterministic hidden tests where possible;
- false-positive rate;
- missed-defect rate.

## Required Metrics

Primary:
- task success;
- DevOpsBench oracle pass;
- first-pass test pass;
- regression count.

Efficiency:
- wall-clock duration;
- model calls;
- tool calls;
- input/output tokens;
- estimated cost when price data is available.

AgentTeam behavior:
- teammate spawn success;
- task-board terminal completion;
- review completion;
- human intervention;
- retry/rework count.

## Repetition

A single successful run is not enough for model selection.

Initial target:
- 3 repetitions per configuration per deterministic case.
- Increase to 5+ after the harness is stable.

Report:
- success rate;
- median duration;
- median token usage;
- failure-mode distribution.

## Guardrails

A model configuration is invalid for AgentTeam comparison if it does not first pass:
- Basic Chat;
- Structured Tool Calling;
- OpenJiuwen role execution;
- deterministic workspace/path guards.

Capability failures are not scored as low-quality benchmark results; they are rejected before the quality benchmark.

## Action Cost Control

To keep GitHub Actions readable and affordable:
- candidate capability probes are non-failing research jobs;
- only required role models use strict gates;
- role benchmarks run only on eligible models;
- no full Cartesian product in V0.1;
- use workflow concurrency for superseded development runs;
- benchmark workflow runs should not use cancel-in-progress once collecting comparable measurements.

## Next Gate

The first heterogeneous baseline must complete successfully:

```text
GLM-5.3 + Qwen3-32B + deepseek-v4.1-flash
            ↓
coding.python.off_by_one.001
            ↓
DevOpsBench oracle PASS
```

Once this passes, E1 Coding-role comparison can begin.
