# 27 — AtomGit Reference Adapter & Multi-SCM Delivery Loop

Date: 2026-09-25  
Status: **Local mock contract smoke verified; live platform compatibility pending**

## 2026-09-26 Evidence Correction

The credential-free smoke uses `FakeAtomGitClient`. Its passing assertions verify local adapter behavior against synthetic responses, not the real API host, endpoint availability, webhook signature protocol or Actions compatibility. The capabilities below are implementation claims pending official-contract and live validation. No remote CI run was identified for this untracked implementation in this assessment. See [assessment](../project-assessment-2026-09-26.md).

## Purpose

Per architectural decision **D-007** and PRD section `07 — SCM & DevOps Provider`, DevOpsPilot is strictly decoupled from proprietary SCM providers. Following the initial GitHub and CNB adapters, the **AtomGit Reference Adapter** provides native support for the AtomGit ecosystem, enabling autonomous delivery across open-source and domestic cloud software platforms.

## Architecture

```text
┌────────────────────────────────────────────────────────┐
│                   DevOpsPilot Core                     │
│  (Delivery Loop, Autonomous Remediation Control Plane) │
└──────────────────────────┬─────────────────────────────┘
                           │ Standard Ports
                           ▼
┌────────────────────────────────────────────────────────┐
│              SCMProvider & CIProvider Ports            │
└──────────────────────────┬─────────────────────────────┘
                           │ Bound to
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│ GitHub Adapter│  │  CNB Adapter  │  │AtomGit Adapter│
└───────────────┘  └───────────────┘  └───────────────┘
                                              │
                                              ▼
                                    https://api.atomgit.com
                                    - Repository / Issues
                                    - Pull Requests / Reviews
                                    - HMAC-SHA256 Webhooks
                                    - Actions Runs / Logs
```

## Supported Capabilities

### 1. AtomGitSCMProvider
- **Capabilities**: `ISSUES`, `CHANGE_REQUESTS`, `REVIEWS`, `WEBHOOKS`, `CHECKS`, `RELEASES`.
- **Repository Metadata**: `get_repository`.
- **Issue Operations**: `list_issues`, `get_issue`.
- **Pull Request Operations**: `create_change_request`, `get_change_request`.
- **Review & Feedback**: `submit_review` (with `APPROVE`, `REQUEST_CHANGES`, `COMMENT`), `add_comment`.
- **Webhook Security**: Verifies incoming webhooks with `HMAC-SHA256` using `x-atomgit-signature` or `x-hub-signature-256`, and normalizes events into canonical `SCMEvent` domain objects.

### 2. AtomGitCIProvider
- **Capabilities**: `RUNS`, `JOBS`, `LOGS`, `TRIGGER`, `CANCEL`, `RETRY`.
- **Workflow / Pipeline Runs**: `get_run`, `list_runs`.
- **Job Log Streaming**: `stream_logs` yielding standardized `CIJobLog` records.
- **Workflow Control**: `trigger`, `cancel`, `retry_failed`.

## Verification Evidence

- Credential-free contract & behavior suite: `experiments/atomgit-reference-adapter-smoke/main.py`.
- Automated assertions verified:
  - `ATOMGIT_SCM_CAPABILITIES_OK`
  - `ATOMGIT_GET_REPOSITORY_OK`
  - `ATOMGIT_ISSUES_OK`
  - `ATOMGIT_CREATE_PR_OK`
  - `ATOMGIT_COMMENT_OK`
  - `ATOMGIT_SUBMIT_REVIEW_OK`
  - `ATOMGIT_WEBHOOK_NORMALIZATION_OK`
  - `ATOMGIT_CI_CAPABILITIES_OK`
  - `ATOMGIT_RUN_DISCOVERY_OK`
  - `ATOMGIT_STREAM_LOGS_OK`
  - `ATOMGIT_CI_OPERATIONS_OK`
