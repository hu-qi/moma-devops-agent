# 06 — DevOpsBench v0.1 Contract

## Goal

Build the evaluation system before building a large Agent product.

Every major claim must become a measurable experiment:
- MoMA routing helps
- AgentTeam helps
- RSI helps

## Case Unit

A DevOpsBench case is a reproducible software-engineering task.

Required dimensions:

```text
identity
fixture
task
constraints
oracle
metrics
budget
risk
provenance
```

## Minimal Case Schema

```json
{
  "id": "coding.python.off_by_one.001",
  "category": "coding",
  "task": "Fix the failing behavior without changing the public API.",
  "fixture": {
    "path": "fixtures/python-off-by-one",
    "entrypoint": "pytest -q"
  },
  "constraints": {
    "allowed_paths": ["src/**", "tests/**"],
    "forbidden_paths": [".github/**"],
    "max_changed_files": 4
  },
  "oracle": {
    "command": "pytest -q",
    "expected_exit_code": 0
  },
  "budget": {
    "timeout_seconds": 300,
    "max_model_calls": 20,
    "max_tool_calls": 60
  },
  "risk": "low"
}
```

## V0.1 Categories

### Coding
Deterministic failing test → valid patch.

### Code Review
Seeded defect(s) → structured findings.

### CI Debug
Build/log failure → root cause + valid repair.

## Metrics

Primary:
- task_success
- regression_free
- first_pass_success
- elapsed_seconds
- model_calls
- tool_calls
- input_tokens
- output_tokens

Team:
- delegation_count
- reviewer_disagreement
- rework_rounds

Evolution:
- baseline_score
- candidate_score
- regression_delta
- evolution_gain

## Required Ablation

```text
A0 fixed model + single agent
A1 MoMA routing + single agent
A2 MoMA routing + AgentTeam
A3 MoMA routing + AgentTeam + evolved artifact
```

## Evaluation Order

Prefer:
1. deterministic executable oracle
2. static rule/linter oracle
3. structured human rubric
4. LLM judge only when unavoidable

## Anti-overfitting

Maintain:
- public/dev cases
- hidden holdout cases
- versioned benchmark set
- candidate cannot inspect hidden oracle

## Initial Target

20–30 high-quality cases.

First milestone may begin with 3 canonical cases, one per V0.1 category, to validate the runner and metric pipeline.
