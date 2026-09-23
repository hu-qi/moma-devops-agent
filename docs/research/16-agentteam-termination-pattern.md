# 16 — AgentTeam Termination Pattern

Date: 2026-09-24  
Status: **V1 runtime stabilization decision**

## Problem Observed

Two live runs using the same valid MoMA role models produced different runtime
termination behavior.

Both runs successfully:
- generated the correct one-line patch;
- ran the deterministic tests successfully;
- produced an independent Review APPROVE verdict.

However, one run completed normally while another remained alive until the
DevOpsPilot 480-second timeout.

The failing run repeatedly logged OpenJiuwen Team state-transition errors such
as:

```text
idle -> running
pending -> completed
starting -> completing
shutdown_requested -> ready
```

The important finding is that these errors occurred **after the software task
was already correct**.

## Root Cause Boundary

This is not evidence of a MoMA model outage.

The same role models had already passed structured Tool Calling and a separate
heterogeneous AgentTeam + DevOpsBench run.

The unstable part is the current OpenJiuwen 0.1.19 Team task/member lifecycle
when the Leader relies on task-board completion and explicit member shutdown as
its termination condition.

## V1 Decision

Task-board/member lifecycle is treated as runtime coordination metadata, not
the source of delivery truth.

V1 uses a sequential dynamic-team protocol:

```text
Leader
  ↓
build team
  ↓
spawn Coding only
  ↓
Coding sends patch + test evidence
  ↓
spawn Review only after coding returns
  ↓
Review independently inspects + reruns tests
  ↓
APPROVE / REJECT message
  ↓
Leader returns immediately
  ↓
DevOpsPilot deterministic gate
  ├─ allowed/forbidden paths
  ├─ git diff
  ├─ independent tests
  └─ DevOpsBench oracle
```

The Leader must not use:
- create_task
- claim_task
- update_task
- task-board COMPLETED state
- manual shutdown_member loops

as delivery completion gates.

## Why This Still Qualifies as AgentTeam

The specialized members are still dynamically created at runtime and use
different MoMA model roles.

The change only moves termination authority from a probabilistic/runtime task
board into DevOpsPilot's deterministic product layer.

## Future

Keep the Team task-board feature available for larger workflows after:
- OpenJiuwen lifecycle behavior is stable under repeated DevOpsBench runs; or
- DevOpsPilot adds an explicit state-reconciliation adapter for Team tasks.

The benchmark should measure both task quality and team termination success.
