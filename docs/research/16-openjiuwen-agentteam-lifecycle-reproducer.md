# 16 — OpenJiuwen AgentTeam Lifecycle Reproducer

Date: 2026-09-24  
Status: **Reproducible in CI; workaround active**

## Symptom

On OpenJiuwen `release/v0.1.19`, a dynamic AgentTeam can complete useful software-engineering work while the Team stream remains open or member/task lifecycle transitions fail.

Observed errors include:

- `Invalid state transition for member review-agent: idle -> running`
- `Invalid state transition for member review-agent: idle -> completing`
- `Invalid state transition for member review-agent: idle -> completed`
- `Invalid state transition for member devops_leader: idle -> running`
- `Invalid state transition for task ...: pending -> completed`
- `Cannot clean team ...: not all members are shutdown`

## Important Control Evidence

A successful TaskExecutor run used the same MoMA role model combination:

    Leader: GLM-5.3
    Coding: Qwen3-32B
    Review: deepseek-v4.1-flash

and still emitted lifecycle transition errors.

Successful run:

    workflow: OpenJiuwen Task Executor
    run: 35900368149

It completed:

- code modification;
- independent review;
- test execution;
- local commit;
- DevOpsBench oracle.

This strongly indicates that the lifecycle errors are not caused by the selected MoMA model combination.

## Timeout Reproduction

Later runs with stricter trajectory/lifecycle capture reproduced the case where:

1. Coding Agent modified the file correctly.
2. Coding Agent produced real diff/test evidence.
3. Review Agent was spawned.
4. Review Agent independently inspected the working tree and ran tests.
5. OpenJiuwen member-state transitions entered inconsistent states.
6. Team stream failed to terminate.
7. DevOpsPilot timeout cancelled the stream.

Example failing runs:

- `35900244574`
- `35901656554`

The terminal error was a DevOpsPilot execution timeout wrapping an `asyncio.CancelledError` while waiting on OpenJiuwen's Team stream queue.

## Current DevOpsPilot Workaround

DevOpsPilot now separates software-delivery correctness from runtime termination health.

On AgentTeam timeout:

1. mark `runtime_degraded=true`;
2. stop the OpenJiuwen Runner;
3. drain canonical trajectory;
4. run independent repository tests;
5. enforce allowed/forbidden changed paths;
6. enforce changed-file budget;
7. run DevOpsBench oracle;
8. accept the task only if deterministic engineering gates pass.

## Why This Is Safe

A runtime timeout never becomes automatic task success.

Success is still determined by repository evidence, not by the Agent's own statement.

## Upstream Candidate

If the behavior remains reproducible after the workaround run, this document can be converted into an upstream OpenJiuwen issue with:

- release branch/commit;
- minimal TeamAgentSpec;
- member transition logs;
- expected vs actual stream completion behavior;
- no DevOpsPilot business dependencies.