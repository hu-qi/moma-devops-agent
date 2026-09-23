# 07 — DevOpsPilot Core Contracts

Date: 2026-09-23  
Status: **Architecture contract baseline**

## Goal

DevOpsPilot 必须可以替换：

- MoMA → 其他 MaaS
- OpenJiuwen Runtime → 新版本或其他 Runtime Adapter
- GitHub → GitCode / AtomGit / Gitee / CNB / GitLink
- GitHub Actions → 其他 CI
- OpenJiuwen RSI → 其他 Evolution Provider

而不重写产品领域层。

因此 Core Contract 不直接引用 OpenJiuwen、GitHub SDK、MoMA SDK 等第三方对象。

## Dependency Rule

```text
DevOpsPilot Domain
       ↓
Core Contracts
       ↓
Adapters
       ↓
OpenJiuwen / MoMA / SCM / CI / RSI
```

第三方类型只能出现在 Adapter 层。

## 1. TaskProfile

TaskProfile 描述“这是什么任务”，而不是“调用哪个模型”。

核心维度：

- task_type
- complexity
- risk_level
- context_size
- reasoning_requirement
- coding_requirement
- review_requirement
- latency_budget
- cost_budget
- privacy_level
- industry / project metadata

## 2. ModelCapability & RoutingDecision

DevOpsPilot 先决定所需能力：

- FAST
- REASONING
- CODING
- REVIEW
- JUDGE

然后 MaaS Provider 将能力要求解析成 RoutingDecision。

RoutingDecision 不携带 Secret，只包含：

- provider
- connection reference
- route mode
- model / managed route alias
- fallback
- decision reason
- observable metadata

## 3. MaaSProvider

MaaSProvider 是 **control-plane contract**，不是重新实现一套 LLM Client。

职责：

```text
TaskProfile
   +
ModelCapability
   ↓
resolve()
   ↓
RoutingDecision
```

真正模型调用继续由 Runtime Adapter（V1 为 OpenJiuwen）完成。

这样避免同时维护：

```text
DevOpsPilot LLM Client
+
OpenJiuwen LLM Client
```

两套重复数据面。

## 4. SCMProvider

SCMProvider 负责把不同 Git 平台映射为统一领域对象。

V1 Contract 覆盖：

- repository
- issue/work item
- branch/commit
- change request (PR/MR)
- comments/reviews
- webhook normalization
- capability discovery

平台原始 JSON 不进入 Orchestration Core。

## 5. CIProvider

CI 与 SCM 分离。

原因：

- SCM 自带 CI 并非唯一情况；
- 企业经常 Git + Jenkins / 自建流水线组合；
- 同一 SCM 未来可能映射不同 CI Provider。

V1：

- run/status
- job/log
- retry
- artifact reference

## 6. Trajectory

Trajectory 是 DevOpsPilot 的 canonical execution evidence。

至少记录：

- task profile
- routing decisions
- team topology
- model/tool actions
- verification events
- human intervention
- final outcome
- benchmark/CI evidence

Trajectory 不保存明文凭据。

OpenJiuwen observability/trajectory 必须投影到 DevOpsPilot Trajectory，而不是成为产品唯一真源。

## 7. EvolutionCandidate

RSI / Skill Evolution 产生 Candidate，而不是直接产生 Production State。

核心对象：

```text
EvolutionCandidate
├─ artifact type
├─ base version
├─ candidate version
├─ source trajectories
├─ change reference
├─ benchmark evidence
└─ promotion status
```

Promotion 必须独立于 Candidate Generation。

## 8. Runtime Adapter Boundary

V1：

```text
DevOpsPilot Contracts
       ↓
OpenJiuwenRuntimeAdapter
       ↓
OpenJiuwen 0.1.19 line
```

Adapter 负责：

- RoutingDecision → Jiuwen Model configuration
- TeamPattern → TeamAgentSpec
- DevOps Tools → Jiuwen Tool/MCP
- Jiuwen trace → DevOpsPilot Trajectory
- OpenJiuwen RSI candidate → EvolutionCandidate

## Decision

从这一阶段起，新业务实现优先依赖 `src/devopspilot/contracts`，不得在 Domain / Orchestration 中直接扩散第三方 SDK 类型。
