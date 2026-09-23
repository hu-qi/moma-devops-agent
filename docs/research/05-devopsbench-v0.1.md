# 05 — DevOpsBench v0.1

Date: 2026-09-23  
Status: **Design started**

## 1. Purpose

DevOpsBench is not a presentation-only scorecard.

It is the objective function for:
- model routing
- single Agent vs AgentTeam
- Skill changes
- Prompt changes
- Team Pattern changes
- RSI candidate promotion

Without DevOpsBench, Self-Evolving has no trustworthy definition of "better".

## 2. v0.1 Scope

Start small and deterministic.

Initial categories:

1. `coding`
2. `code-review`
3. `ci-debug`

Target: 20–30 high-quality cases after the contract is stable.

The first milestone starts with 3–5 cases.

## 3. BenchmarkCase Contract

Required fields:

```text
id
version
category
title
description

fixture
task

allowed_changes
forbidden_changes

setup_command
test_command
verification_command

expected_outcome
risk_level

timeout_seconds
tags
```

Optional:
- industry
- visible_tests
- holdout_tests
- seeded_failure
- expected_findings
- scoring_weights

## 4. EvaluationResult Contract

```text
case_id
run_id
variant

status
task_success

test_pass
ci_pass
regression_count

duration_ms
model_calls
tool_calls
input_tokens
output_tokens
estimated_cost

human_interventions
artifacts
failure_reason
```

## 5. Deterministic-first Scoring

Priority order:

1. executable tests
2. static/deterministic rule checks
3. expected structured findings
4. LLM Judge only when deterministic verification is insufficient

The LLM Judge must never be the only criterion for a code task that can be compiled or tested.

## 6. Initial Ablation Variants

```text
baseline-fixed-single
moma-routed-single
moma-routed-team
moma-routed-team-evolved
```

Every run carries the variant id.

## 7. First Fixtures

### D001 — Python bug fix
A small deterministic functional bug with explicit tests.

Goal:
- validate code modification loop
- validate no unrelated changes

### D002 — CI dependency failure
Repository builds locally only after correcting a dependency/config mismatch.

Goal:
- validate log-driven diagnosis
- become first build-debug Skill RSI target

### D003 — Code review defect set
A patch contains several known defects.

Goal:
- measure reviewer findings
- compare single model vs independent Reviewer

## 8. RSI Promotion Rule

Initial candidate promotion requires:

```text
target metric improves
AND no critical regression
AND deterministic gates pass
AND holdout performance does not materially degrade
AND candidate is versioned + rollbackable
```

Human approval remains required for production promotion.

## 9. Next Implementation Step

Create:
- machine-readable case schema
- evaluation result schema
- D001 fixture
- local runner skeleton

Then run the same D001 through a baseline agent and AgentTeam.
