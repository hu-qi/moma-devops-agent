# 08 — SCM / CI Capability Matrix

Date: 2026-09-23  
Status: **Round 1 public API/documentation research completed; credentialed adapter smoke tests pending**

## 1. Goal

Validate whether DevOpsPilot's provider boundary can support both GitHub and major domestic Git platforms without leaking platform-specific semantics into the product core.

The V1 product needs two related but independent contracts:

- `SCMProvider`: repository, Issue/work item, PR/MR, review, comment, webhook.
- `CIProvider`: pipeline/run status, jobs, logs, retry/trigger, artifacts.

A platform can therefore be a strong SCM provider even when its CI API is incomplete.

## 2. Capability Matrix

Legend:

- **YES** — current public documentation/API clearly supports the capability.
- **PARTIAL** — capability exists but has documented gaps/access constraints.
- **UNKNOWN** — public evidence is insufficient; requires account/API verification.

| Platform | Repo API | Issue | PR/MR | Review | Webhook | CI/Pipeline API | CI Logs | Retry/Trigger | Auth | V1 Assessment |
|---|---|---|---|---|---|---|---|---|---|---|
| GitHub | YES | YES | YES | YES | YES | YES | YES | YES | App / PAT | Reference adapter |
| GitCode | YES | YES | YES | YES | YES | YES | YES | YES | PAT / OAuth-like token flows | High priority domestic |
| AtomGit | YES | YES | YES | YES | YES | YES | YES | YES | PAT / Bearer | High priority domestic |
| Gitee | YES | YES | YES | YES | YES | **PARTIAL** | **NO public Gitee Go API verified** | **PARTIAL** | OAuth / access token | SCM strong, CI weak |
| CNB | YES | YES | YES | YES | YES / event-driven build | YES | YES | YES | Bearer token | High priority domestic |
| GitLink | YES | YES | YES | YES | YES | YES via current CLI/API layer | YES | YES | GITLINK_TOKEN / platform auth | Promising, smoke test required |

## 3. GitHub

### Confirmed

GitHub remains the reference implementation because its REST API exposes:
- repositories;
- Issues;
- Pull Requests;
- review requests;
- review creation/submission;
- webhook event payloads;
- Actions workflow runs;
- jobs/logs/artifacts/re-run operations.

This gives DevOpsPilot a mature reference semantics for both `SCMProvider` and `CIProvider`.

### Role in DevOpsPilot

GitHub should be the **contract reference adapter**, not the product's hard-coded domain model.

Sources:
- https://docs.github.com/en/rest/issues/issues
- https://docs.github.com/en/rest/pulls/pulls
- https://docs.github.com/en/rest/pulls/reviews
- https://docs.github.com/en/rest/actions/workflow-runs
- https://docs.github.com/en/webhooks/webhook-events-and-payloads

## 4. GitCode

### Confirmed SCM Surface

GitCode's current OpenAPI documentation exposes API v5 and PAT authentication:

```text
https://api.gitcode.com/api/v5/...
```

The documentation navigation explicitly covers:
- Repositories
- Issues
- Pull Requests
- Webhooks
- Releases
- Actions

PR payloads expose reviewers/approvers, review state, merge checks and CI-related merge gates.

Webhooks cover at least:
- Commit
- Issue
- Pull Request
- Tag Push
- Note/comment

### Confirmed Actions / CI Surface

Current OpenAPI documentation also exposes an Actions API family, including:
- stop a run;
- retry failed jobs;
- rerun a workflow;
- manually run a workflow;
- list workflows;
- list workflow runs;
- get run details;
- list jobs;
- get job details;
- query step-level logs;
- download job logs;
- list/download artifacts;
- query runners.

Notably, current Action endpoints use an `/api/v8/.../actions/...` family while general SCM APIs are documented under `/api/v5`.

### Assessment

GitCode can support a full DevOpsPilot loop and should be one of the first domestic adapters.

Sources:
- https://docs.gitcode.com/docs/apis/
- https://docs.gitcode.com/docs/help/home/org_project/webhook/
- https://docs.gitcode.com/docs/apis/post-api-v-8-repos-owner-repo-actions-runs-run-id-stop

## 5. AtomGit

### Confirmed SCM Surface

AtomGit has its own API host:

```text
https://api.atomgit.com/api/v5/...
```

Its OpenAPI navigation explicitly includes:
- Repositories
- Issues
- Pull Requests
- Webhooks
- Actions
- OAuth2

It supports PAT through Authorization Bearer, PRIVATE-TOKEN, or query access token forms.

### Confirmed Action Surface

AtomGit Action supports:
- push;
- pull_request;
- pull_request_comment;
- workflow_dispatch;
- Issue-related events;
- workflow/job/step execution.

Its OpenAPI Actions section exposes run/job/log/artifact management comparable in shape to the GitCode documentation.

### Important Constraint

Current quick-start documentation states that code-based pipeline capability may require platform enablement/contact with AtomGit support. The API shape is strong, but account-level availability must be tested before selecting it for a live competition demo.

### Assessment

Keep AtomGit as a separate provider ID from GitCode even if implementations share protocol/client code. Do not assume endpoint/account/feature parity.

Sources:
- https://docs.atomgit.com/docs/apis/
- https://docs.atomgit.com/docs/help/home/org_project/pipeline/syntax-reference/trigger-events/
- https://docs.atomgit.com/docs/help/home/org_project/pipeline/quick-start/

## 6. Gitee

### SCM Strength

Gitee API v5 has mature repository operations. Public SDK/API artifacts confirm repository WebHook CRUD, and Gitee's current platform documentation supports Issue, Pull Request, comments and repository webhooks.

A current Gitee-maintained MCP project also exposes tools for:
- repositories;
- Issues;
- Pull Requests;
- PR diff;
- PR review;
- comments.

### CI Gap

A Gitee Feedback request opened on 2026-04-02 documents that Gitee Go currently lacks the public REST surface required for:
- listing pipeline runs;
- querying jobs;
- retrieving build logs;
- triggering/retrying runs through a public Pipeline API;
- receiving pipeline state through repository webhooks.

The request explicitly notes that Gitee API v5 already covers repository/Issue/PR use cases well while the Gitee Go Pipeline API is missing.

This is a material DevOpsPilot limitation because automated CI RCA requires machine-readable build status and logs.

### Assessment

Implement Gitee as an `SCMProvider`, but do **not** claim a complete native `CIProvider` until a current API is verified.

Potential fallback approaches:
- external CI provider;
- repository check/status APIs where appropriate;
- user-provided generic CI webhook/log adapter.

Sources:
- https://gitee.com/sdk/gitee5j/blob/main/docs/WebhooksApi.md
- https://gitee.com/oschina/mcp-gitee
- https://gitee.com/oschina/git-osc/issues/IHWZMT

## 7. CNB

### Confirmed OpenAPI

CNB officially publishes:
- API service/documentation at `https://api.cnb.cool`;
- Swagger JSON at `https://api.cnb.cool/swagger.json`;
- Bearer token authentication.

### Confirmed Agent-Friendly Surface

CNB's official Skills documentation, built on OpenAPI, lists:

SCM:
- repository management;
- Issue create/comment/close/labels;
- PR create/review/merge/status;
- branches/tags/releases;
- inline code review.

CI/CD:
- pipeline configuration and triggering;
- build log querying;
- build status querying.

The build system supports events from:
- Git operations;
- PR operations;
- Issue events;
- API triggers;
- scheduled tasks.

### Assessment

CNB is particularly attractive for DevOpsPilot because the platform already exposes the exact surfaces an autonomous DevOps Agent needs: repo + Issue/PR + pipeline + logs.

It should be a top candidate for the first fully domestic end-to-end adapter.

Sources:
- https://docs.cnb.cool/zh/develops/openapi.html
- https://docs.cnb.cool/zh/develops/skills.html
- https://docs.cnb.cool/zh/build/trigger-rule.html
- https://docs.cnb.cool/zh/build/quick-start.html

## 8. GitLink

### Confirmed SCM API

GitLink's API reference contains:
- project/repository operations;
- file/branch/commit operations;
- repository webhook CRUD/history/test;
- Pull Request list/create/diff/commits;
- Pull Request review list/create;
- PR comments;
- Issues.

### Current Agent/CLI Surface

The current official `Gitlink/gitlink-cli` project is explicitly designed for humans and AI Agents and advertises:
- repository management;
- Issues;
- PR create/merge/review;
- WebHook management/test/delivery;
- CI build status/logs;
- pipeline run/inspect/enable/disable/delete/logs;
- structured output;
- `GITLINK_TOKEN` support for CI/non-interactive use.

This is stronger evidence than the older standalone API reference for current DevOps usage, but we still need a credentialed smoke test to determine the stable raw API endpoints behind the CLI.

### Assessment

GitLink should remain in V1 architecture and is no longer treated as a low-capability platform. For implementation, evaluate whether to:
1. use its raw API directly; or
2. temporarily wrap `gitlink-cli` as an adapter while stabilizing endpoint coverage.

Sources:
- https://www.gitlink.org.cn/docs/api
- https://www.gitlink.org.cn/Gitlink/gitlink-cli
- https://help.gitlink.org.cn/

## 9. Key Architecture Findings

### Finding A — SCMProvider and CIProvider must remain separate

The Gitee case proves this separation is necessary.

```text
GiteeProvider : SCMProvider
GenericCI / external CI : CIProvider
```

A single platform adapter must not be assumed to provide both.

### Finding B — Capability discovery is mandatory

Provider behavior should use capabilities rather than provider-name conditionals.

Example:

```python
if SCMCapability.REVIEWS in await scm.capabilities():
    ...
```

CI should have an equivalent explicit capability contract in a future revision.

### Finding C — PR and review semantics differ

Normalized DevOpsPilot models need to represent:
- PR/MR state;
- reviewers;
- approval/rejection/comment review states;
- inline comments/discussions;
- merge gates;
- CI/check status.

The current `SCMProvider` contract is intentionally minimal, but the matrix shows that V1 will need a review operation before the full delivery loop is implemented.

### Finding D — GitCode and AtomGit share concepts, not identity

Both currently expose similar API families and Action concepts, but they have distinct hosts, tokens and feature rollout constraints.

Keep:
- `gitcode`
- `atomgit`

as separate provider IDs. Shared adapter internals are allowed.

## 10. Provisional V1 Adapter Order

This is a technical implementation order, not a product ranking.

### Wave 1 — Reference + domestic full-loop

1. **GitHub** — reference contract and easiest deterministic test target.
2. **CNB** — strongest documented domestic full-loop surface for repo/PR/CI/logs.
3. **GitCode** — strong SCM + Actions API and important domestic ecosystem target.

### Wave 2

4. **AtomGit** — technically strong, validate account/pipeline enablement.
5. **GitLink** — broad current CLI/Agent surface; verify raw API stability.

### Wave 3

6. **Gitee** — implement SCM fully; pair with external/generic CI until Gitee Go exposes the required public CI APIs.

## 11. Next Spikes

### SCM-S1 — Provider Contract Test Suite

Build provider-neutral contract tests against fixtures:
- normalize webhook;
- get repository;
- get Issue;
- create PR/MR;
- add comment;
- submit review.

### SCM-S2 — GitHub Reference Adapter

Implement the contract once against GitHub and make the tests executable.

### SCM-S3 — First Domestic Adapter

Prefer CNB or GitCode based on which credential/test account is available first.

### CI-S1 — CI Capability Contract

Extend CI capability modelling for:
- runs;
- jobs;
- logs;
- retry;
- trigger;
- cancel;
- artifacts.

### CI-S2 — Domestic CI Probe

Run one failing build and verify DevOpsPilot can:
1. observe failure;
2. retrieve logs;
3. normalize the run/job state;
4. retry after a code fix.

## 12. Decision

The multi-SCM architecture is technically justified and feasible.

No change is required to the high-level PRD decision. The next implementation should be provider contract tests + GitHub reference adapter, while the first domestic end-to-end adapter should be selected from CNB / GitCode based on live credential availability.
