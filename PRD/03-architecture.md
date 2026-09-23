# 03 — V1 Architecture

## 1. Architecture Principle

产品层与第三方 Runtime、MaaS、SCM 均通过清晰边界解耦。

```text
Interaction
    ↓
DevOps Gateway
    ↓
DevOps Leader
    ↓
Task Profiler / Planner
    ↓
Single Agent | AgentTeam
    ↓
Model Intelligence
    ↓
OpenJiuwen Runtime
    ↓
Skills / Tools / Providers
    ↓
SCM / CI / Shell / Cloud
    ↕
Trajectory / Evaluation / Evolution
```

## 2. Logical Layers

### Interaction Layer

来源：
- SCM Webhook
- Issue / PR / MR
- Chat
- CLI
- API

### DevOps Gateway

职责：
- Event normalize
- Identity / tenant context
- Repository binding
- Session binding
- Idempotency
- Event safety

### Orchestration Layer

核心：
- DevOps Leader
- TaskProfiler
- Planner
- Complexity Gate
- Team Builder
- Verifier

简单任务走单 Agent；复杂任务动态创建 Team。

### Model Intelligence Layer

职责：
- TaskProfile
- ModelCapabilityProfile
- Routing Policy
- MaaS Provider
- routing metrics

比赛默认 Provider：MoMA。

### Agent Runtime Layer

OpenJiuwen Agent Core 提供：
- Harness
- Agent / AgentTeam runtime
- Skill / Tool integration
- Session / checkpoint
- Permission / HITL 基础能力
- RSI / evolving 基础设施（按实际稳定 API 接入）

DevOpsPilot 不复制 Runtime 源码。

### Domain Capability Layer

自主实现：
- DevOps Skills
- SCM Tools
- CI Tools
- Domain prompts
- Team Patterns
- Verification policy
- Industry Packs

### Evaluation & Evolution Layer

```text
Trajectory Store
    ↓
Analyzer
    ↓
Candidate Generator
    ↓
DevOpsBench
    ↓
Regression Gate
    ↓
Human Approval
    ↓
Artifact Registry
```

## 3. Proposed Repository Structure

```text
moma-devops-agent/
├── PRD/
├── src/
│   └── devopspilot/
│       ├── gateway/
│       ├── orchestration/
│       ├── agents/
│       ├── model_intelligence/
│       ├── providers/
│       │   ├── maas/
│       │   ├── scm/
│       │   └── ci/
│       ├── tools/
│       ├── evolution/
│       ├── evaluation/
│       └── domain/
├── skills/
├── industry-packs/
├── evals/
├── tests/
└── docs/
```

## 4. Dependency Direction

必须保持单向依赖：

```text
Product Domain
    ↓
Ports / Contracts
    ↓
Adapters
    ↓
OpenJiuwen / MoMA / SCM APIs
```

禁止业务层直接散落调用 GitHub/Gitee/MoMA/OpenJiuwen 私有实现。

## 5. Core Contracts to Define Before Coding

- TaskProfile
- ModelCapabilityProfile
- MaaSProvider
- SCMProvider
- CIProvider
- AgentExecutionContext
- TeamPattern
- Trajectory
- EvolutionArtifact
- BenchmarkCase
- EvaluationResult

这些 Contract 是下一阶段 PoC 的优先探索对象。
