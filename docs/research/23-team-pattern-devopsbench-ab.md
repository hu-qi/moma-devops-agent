# 23 — Team Pattern DevOpsBench A/B

Date: 2026-09-24
Status: **Manual live evaluation prepared**

## Hypothesis

A reusable validated Swarm Skill can improve the current dynamic AgentTeam's completion/termination behavior by making role dependencies, reviewer handoff, Leader finalization, timeout handling and degraded-mode behavior explicit.

## Controlled comparison

Both variants use:
- the same coding.python.off_by_one.001 DevOpsBench fixture;
- the same MoMA Leader/Coding/Review model routing;
- the same OpenJiuwen runtime;
- the same path constraints and independent tests.

Only the candidate variant mounts the generated Team/Swarm Skill through OpenJiuwen's skill_use rail.

## Gate

Primary desired improvement:

    runtime_clean_completion: false -> true

Hard requirements:
- no task_success regression;
- no increase in deterministic regression_count;
- candidate task must succeed;
- some measurable improvement must exist.

If the gate passes, state becomes PENDING_HUMAN.

It never auto-promotes to production.
