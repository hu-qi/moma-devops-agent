# 22 — Governed Swarm Skill Candidate Pipeline

Date: 2026-09-24
Status: **Implementation / live validation**

## Boundary

The existing real Team Pattern proposal remains pending human approval.

DevOpsPilot now separates:

    proposal
      -> TeamPatternCreationDecision
      -> sandbox candidate generation
      -> official JiuwenSwarm validation
      -> DevOpsBench A/B
      -> RegressionGate
      -> human promotion decision

No stage before the final promotion decision writes production Skills.

## Creator dependency

The candidate generator uses JiuwenSwarm's official swarmskill-creator as an external dependency, pinned to commit:

    6ab1ed59a8c455cdb9dfe45db34a3a8d42c10d47

DevOpsPilot does not vendor/copy that creator into this repository.

## Structured generation

MoMA is required to call one function:

    emit_swarm_skill_candidate(files=[...])

The V1 candidate shape is the full Markdown Swarm Skill spec:
- SKILL.md
- roles/*.md
- workflow.md
- bind.md
- dependencies.yaml

Executable workflow.py is deliberately excluded from the first Team Pattern candidate. The initial hypothesis is that explicit role boundaries, dependencies, completion criteria and timeout/degraded-mode contracts should be tested before introducing executable orchestration code.

## Validation

The generated bundle is materialized only under a temporary/artifact directory and must pass JiuwenSwarm's official validate_swarmskill.py.

A failed official validator means no EvolutionCandidate is returned.

## Governance

A PENDING_HUMAN or REJECTED proposal raises before any model call.

The CI experiment uses only a synthetic APPROVED proposal to verify infrastructure. The real proposal from repeated AgentTeam timeout evidence is not automatically approved.


## Creator Failure Evidence and V2 Strategy

The first live creator implementation asked one MoMA model call to emit the entire
seven-file Swarm Skill bundle through one structured tool call.

Live evidence showed this is the wrong artifact-generation shape:

- model: GLM-5.3
- max_tokens: 12000
- result: finish_reason=length
- tool_calls: none
- content: none
- reasoning_content: the model correctly planned the complete Swarm Skill, but
  exhausted the output budget before it reached the structured tool call.

This is not a JiuwenSwarm validator failure and not a MoMA connectivity failure.

DevOpsPilot V2 candidate creation therefore uses staged composition:

~~~text
approved proposal
      ↓
fixed candidate identity + role manifest
      ↓
SKILL.md          ┐
roles/leader.md   │
roles/coding.md   │  bounded structured calls
roles/review.md   ├─────────────────────────┐
workflow.md       │                         │
bind.md           ┘                         │
dependencies.yaml = deterministic sandbox  │
                                            ↓
                                   canonical bundle
                                            ↓
                              official JiuwenSwarm validator
                                            ↓
                                  EvolutionCandidate
~~~

Each model call receives only the relevant official JiuwenSwarm template and a
small set of cross-file invariants. This reduces token pressure and localizes
generation failures to one file.

The sandbox V1 dependency manifest is deliberately deterministic:

~~~yaml
skills: []
tools: []
~~~

This prevents cross-file dependency hallucination while evaluating the Team
Pattern itself. Dependency enrichment is a separate governed step and is not
part of the first runtime-completion hypothesis.

The real repeated-timeout Team Pattern proposal remains PENDING_HUMAN. Staged
generation is currently exercised only with a synthetic approval.
