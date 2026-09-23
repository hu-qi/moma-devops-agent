# 11 — CNB OpenAPI Contract Mapping

Date: 2026-09-23  
Status: **Official Swagger mapped; credentialed live adapter test pending**

## Evidence Source

Canonical source:

```text
https://api.cnb.cool/swagger.json
```

The Swagger identifies itself as `CNB OPENAPI` and is linked by CNB's official developer documentation.

## SCM Mapping

### Repository

```text
GET /{repo}
operationId: GetByID
response: dto.Repos4User
```

DevOpsPilot:
- `id` → `RepositoryRef.repository_id`
- `slug` → `RepositoryRef.full_name`
- default/main branch if exposed → `default_branch`
- `web_url` or canonical CNB URL → `web_url`

### Issue

```text
GET /{repo}/-/issues/{number}
operationId: GetIssue
response: api.IssueDetail
```

Fields confirmed by schema:
- number
- title
- body
- state
- author
- labels

These map directly to `WorkItemRef`.

### Pull Request

```text
GET  /{repo}/-/pulls/{number}  -> api.Pull
POST /{repo}/-/pulls           -> api.Pull
```

Confirmed fields:
- number
- title
- state
- head.ref
- base.ref
- reviewers / mergeable state

CNB refs are represented as values such as `refs/heads/main`; the adapter normalizes them to branch names.

### Review

```text
GET/POST /{repo}/-/pulls/{number}/reviews
```

Review request event values:
- approve
- comment
- request_changes
- pending

Persisted review states:
- approved
- commented
- changes_requested
- dismissed
- pending

DevOpsPilot maps only its canonical:
- APPROVE
- COMMENT
- REQUEST_CHANGES

The POST response is documented as HTTP 201 without a response schema, therefore `submit_review()` resolves the persisted review through the list endpoint when necessary.

## CI Mapping

### Trigger

```text
POST /{repo}/-/build/start
operationId: StartBuild
response: dto.BuildResult
```

Confirmed response fields:
- sn
- buildLogUrl
- message
- success

`sn` is the canonical CNB build/run ID.

### Status

```text
GET /{repo}/-/build/status/{sn}
operationId: GetBuildStatus
response: dto.BuildStatusResult
```

Confirmed structure:

```text
status
pipelinesStatus:
  <key>:
    id
    name
    status
    stages:
      - id
        name
        status
```

### Stage Logs

```text
GET /{repo}/-/build/logs/stage/{sn}/{pipelineId}/{stageId}
operationId: GetBuildStage
response: dto.BuildStageResult
```

Confirmed fields:
- id
- name
- status
- content[] (one log line per item)
- error
- duration/start/end

This gives DevOpsPilot a deterministic mapping:

```text
BuildStatus
  ↓
Pipeline
  ↓
Stage
  ↓
GetBuildStage
  ↓
CIJobLog
```

### Cancel

```text
POST /{repo}/-/build/stop/{sn}
operationId: StopBuild
```

### Retry

The current Swagger contains no dedicated retry/rerun operation.

Therefore:
- `CNBCIProvider.retry_failed()` raises `NotImplementedError`.
- `CICapability.RETRY` is not advertised.

A new build may be triggered explicitly, but it must not be mislabeled as a native retry.

### Artifacts

CNB has artifact APIs, but build → produced-artifact correlation has not yet been live-verified for this adapter.

Therefore:
- `CICapability.ARTIFACTS` is not advertised yet.
- `list_artifacts()` returns no claimed mapping until that evidence exists.

## Event Ingress

CNB officially exposes repository Events, including:
- IssueEvent
- IssueCommentEvent
- PullRequestEvent
- PullRequestReviewEvent
- PushEvent
- ReleaseEvent

The adapter can normalize those event objects through `normalize_webhook()`, but **SCMCapability.WEBHOOKS is intentionally not advertised** until a true external webhook delivery mechanism is verified.

This distinction prevents polling/event-history support from being misrepresented as webhook support.

## Implementation

Current files:

```text
src/devopspilot/adapters/cnb/client.py
src/devopspilot/adapters/cnb/scm.py
src/devopspilot/adapters/cnb/ci.py
```

Transport choices:
- `CNBHTTPClient`: direct official OpenAPI; preferred product transport.
- `CNBCLIClient`: official CLI transport retained for exploration/ops use.

## Next Gate

Credential-free behavior smoke must pass first.

Then a CNB test token/repository will be used to verify:

```text
Repository → Issue → PR → Review
Build trigger → status → stage logs → cancel
```

No CNB credential is needed until that live integration gate.
