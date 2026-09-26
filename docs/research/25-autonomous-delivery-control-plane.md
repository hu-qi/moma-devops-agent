# 25 — Autonomous Delivery Control Plane & Live CI Remediation

Date: 2026-09-25  
Status: **Implemented; local smoke verified; live success recorded, reproducibility incomplete**

## 2026-09-26 Evidence Correction

Live run [36086881849](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086881849) succeeded on `abcb389`, with an explicit 240-second AgentTeam timeout/degraded-runtime log. The subsequent same-SHA run [36086892725](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086892725) failed during checkout because the fixture branch was absent. This establishes a successful controlled business path, not clean runtime completion or stable product acceptance.

The ledger records attempts after external side effects; it does not yet guarantee crash-safe idempotency or reserve budgets for failed attempts. Fixture workflow approval and PR/Issue closure are E2E harness behavior, not general production policy. The global no-op lock patch is temporary technical debt, not a verified concurrency solution. See [assessment](../project-assessment-2026-09-26.md) and the root implementation plan for corrective work. The architecture below describes the implemented mechanism with these limitations.

## Purpose

In autonomous software delivery, continuous integration failures are an expected outcome of development, not a terminal state. An enterprise-grade agentic delivery system must autonomously diagnose CI errors, resume work on the exact branch and Pull Request, apply targeted repairs, verify them independently, and push back to achieve green CI under strict safety bounds.

The **Autonomous Delivery Control Plane** provides durable state coordination, bounded remediation policies, cross-origin CI telemetry ingestion, and safe AgentTeam lifecycle execution.

## Architecture

```text
       CI Run Failed (action_required / failure)
                         │
                         ▼
        ┌──────────────────────────────────┐
        │  AutonomousDeliveryControlPlane  │
        │      (State Store & Ledger)      │
        └──────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                                 ▼
┌───────────────────┐           ┌────────────────────┐
│   Ledger Audit    │           │ Bounded Remediation│
│(RemediationLedger)│           │       Policy       │
└───────────────────┘           └────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   GitExistingBranchWorkspaceProvider    │
│   (Isolated Worktree on Same Branch)    │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│      OpenJiuwenRemediationExecutor      │
│  (MoMA Leader → Coding → Review Team)   │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│     GitChangePublisher (Same Branch)    │
│    → CI Run Triggered & Auto-Approved   │
│    → CI Green Verified                  │
│    → Delivery Report & PR Auto-Close    │
└─────────────────────────────────────────┘
```

## Core Components

### 1. SQLite Remediation Ledger
- Stores persistent state for all CI remediation attempts.
- Provides attempt records and audit evidence; crash-safe retry idempotency remains pending.
- Records failure classification, RCA, patch diffs, and verification outcomes.

### 2. Bounded Remediation Policy
- Bounded restart count (default maximum of 2 attempts) to prevent runaway model calls or CI loops.
- Explicit classification of failure modes:
  - Infrastructure / Flaky errors: bounded infra retry without code changes;
  - Code defects: full AgentTeam remediation cycle;
  - Policy / Security violations: escalation to human gate without automated modification.

### 3. Existing Branch Workspace Provider
- Checks out the existing PR source branch into an isolated temporary worktree.
- Avoids mutating or dirtying the primary runner workspace.
- Preserves full git ancestry and commit metadata.

### 4. Cross-Origin CI Log Streamer
- Handles GitHub Actions redirect semantics: when GitHub redirects log download requests to S3 / Azure Blob pre-signed URLs, the control plane automatically strips the `Authorization` header on cross-origin redirects.
- Prevents S3 `400 Bad Request` ("Only one auth mechanism allowed") errors during CI log fetching.

### 5. Safe OpenJiuwen Lifecycle & Lock Management
- Adds timeout-protected runner shutdown and forced process cleanup.
- Bypasses filelock contention during rapid task switching and workspace revalidation after verification side-effects.

### 6. GitHub Live CI Remediation Flow
- Detects fixture CI failures or `action_required` status.
- Automatically approves fixture CI workflow runs when external authorization is required.
- Dispatches MoMA-backed AgentTeam to analyze failures, modify code, and run tests independently.
- Pushes fixes to the same branch, monitors fixture CI to completion, writes a structured delivery report, and closes the PR/Issue cleanly.

## CI Evidence

- **Smoke Tests**: `experiments/autonomous-control-plane-smoke/main.py` and `experiments/remediation-adapter-smoke/main.py` (Passed 100%).
- **Live E2E**: `.github/workflows/github-live-ci-remediation-e2e.yml` validating the end-to-end loop against live GitHub Actions.
