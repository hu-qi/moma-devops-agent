# 07 — SCM & DevOps Provider

## 1. Principle

GitHub 只是一个 Adapter，不是 DevOpsPilot Core。

V1 架构必须覆盖国产研发平台接入。

目标平台：
- GitHub
- GitCode
- AtomGit
- Gitee
- CNB
- GitLink

未来：
- GitLab
- CodeArts Repo
- 企业自建平台

## 2. SCMProvider Contract

统一抽象以下能力：

### Repository
- get repository
- clone / fetch metadata
- branch / commit
- file / diff

### Work Item
- issue
- comment
- labels / state

### Change Request
- PR / MR
- review
- comment
- merge state

### Event
- webhook verification
- normalized event
- idempotency key

### CI Integration
若 SCM 自带 Pipeline，Provider 可暴露标准 CI 引用；复杂 CI 由独立 CIProvider 处理。

## 3. Normalized Domain Objects

禁止业务层直接依赖平台原始 JSON。

核心模型：
- RepositoryRef
- UserRef
- IssueRef
- ChangeRequestRef
- CommitRef
- BranchRef
- WebhookEvent
- PipelineRef
- ArtifactRef

## 4. Provider Capability Discovery

不同平台功能并不完全一致。

Provider 需要暴露 capability matrix，例如：

```text
issues
pull_requests
merge_requests
reviews
checks
pipelines
artifacts
releases
webhooks
draft_changes
```

Agent 根据能力降级，而不是假设所有平台等价。

## 5. GitCode / AtomGit

在产品层分别保留 Provider 边界。

若后续 API 与账号体系完全统一，可在 Adapter 实现层共享客户端或合并，不提前把平台差异写死。

## 6. CIProvider

建议与 SCM 解耦：

```text
CIProvider
├── GitHubActions
├── GiteePipeline
├── CNBPipeline
├── GitCodeCI
└── GenericWebhookCI
```

标准能力：
- get status
- get runs/jobs
- get logs
- retry
- cancel
- artifacts

## 7. Security

- Token / credential 不进入 Prompt。
- Tool 只拿最小权限临时凭据。
- Webhook 必须验签。
- 日志与 Trajectory 必须脱敏。
- Agent 不可自行扩大平台权限。

## 8. Exploration Requirement

进入编码前，为每个目标 SCM 建立 capability matrix，验证：
- API 可用性
- OAuth/PAT
- Webhook
- Issue
- PR/MR
- Review
- CI
- Rate limit
- SDK 成熟度
- 测试账号成本

以此决定 V1 实际实现优先级。
