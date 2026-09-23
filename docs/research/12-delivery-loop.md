# 12 — Provider-Neutral Delivery Loop

Date: 2026-09-23  
Status: **CI verified first product-core loop**

## Why this is a milestone

The project has moved beyond framework and platform exploration.

Verified foundations now include:

- MoMA + OpenJiuwen Model / DeepAgent: live
- Streaming + Tool Calling: live
- Dynamic AgentTeam: live
- RSI runtime injection: live
- Core Provider contracts: CI
- GitHub reference adapter: CI
- CNB reference adapter: CI
- DevOpsBench: CI

The new DeliveryLoop is the first DevOpsPilot-owned orchestration that composes those boundaries without importing a platform SDK.

## Boundary

~~~text
                   DeliveryLoop
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
    SCMProvider    TaskExecutor    CIProvider
        │              │              │
  GitHub / CNB    OpenJiuwen     Actions / CNB
                  adapter next
~~~

DeliveryLoop does not depend on GitHub, CNB, MoMA or OpenJiuwen types.

## State machine

~~~text
RECEIVED
   ↓
EXECUTED
   ↓
CHANGE_OPENED
   ↓
CI_PENDING
  ↙      ↘
CI_FAILED CI_PASSED
   \      /
    verify
      ↓
VERIFIED / REJECTED
~~~

The state is resumable. DevOpsPilot does not need a hidden background polling loop; webhook/event delivery can call reconcile_ci again whenever CI changes.

## Contract findings from real platforms

### Typed comment targets

GitHub uses the Issues comment API for both Issue and PR conversation, while CNB publishes separate Issue and Pull comment APIs.

The canonical contract therefore distinguishes:

- WORK_ITEM
- CHANGE_REQUEST

### CI run discovery

A PR/MR often starts CI automatically. The orchestration must discover that run rather than always trigger a second build.

CIProvider now supports run discovery by:

- commit SHA
- source branch/ref
- optional status

GitHub maps these selectors to Actions workflow-run filters.
CNB maps them to build-history filters.

## DeliveryLoop CI result

Workflow:

~~~text
Delivery Loop
run 35879543573
result success
~~~

The smoke verified this sequence:

~~~text
CHANGE_OPENED
→ CI_PENDING
→ CI_FAILED + captured logs
→ REJECTED
→ later CI event
→ CI_PASSED
→ VERIFIED
~~~

This proves the orchestration can recover from CI state transitions without losing delivery state.

## Next runtime integration

The next adapter is TaskExecutor:

~~~text
DeliveryTask
   ↓
Task profiling / Complexity Gate
   ↓
Single DeepAgent or Dynamic AgentTeam
   ↓
Repository workspace
   ↓
code change + tests
   ↓
commit + publish
   ↓
ExecutionResult
   ↓
DeliveryLoop
~~~

The first live target will be an existing deterministic DevOpsBench coding fixture before remote repository publication is enabled.

This preserves the design rule:

> Single Agent First, Team When Needed.

AgentTeam is available from the beginning, but trivial benchmark tasks should not be forced into a multi-agent topology merely for demonstration.
