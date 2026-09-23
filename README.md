# DevOpsPilot

> **MoMA 驱动的自进化多智能体研发交付系统**

DevOpsPilot 是面向政务、金融、工业、医疗等行业的软件研发智能底座。它以移动云 MoMA 作为默认 MaaS / 多模型调度平台，以 OpenJiuwen Agent Core 作为核心 SDK / Runtime 依赖，通过动态 AgentTeam、行业工程知识、DevOps Skills & Tools、DevOpsBench 与 Self-Evolving / RSI，构建从需求理解、代码实现、测试评审到 CI/CD 交付的自主研发闭环。

## Product Formula

```text
DevOpsPilot
= MoMA Model Intelligence
+ OpenJiuwen Agent Runtime
+ Dynamic DevOps AgentTeam
+ Industry Engineering Packs
+ DevOps Skills & Tools
+ DevOpsBench
+ Self-Evolving / RSI
```

## Core Loop

```text
Understand → Plan → Develop → Review → Verify → Deliver → Observe → Evolve
```

## Design Principles

- **Industry-ready foundation**：Core 保持行业无关，政务、金融、工业、医疗通过 Industry Engineering Pack 扩展。
- **Single Agent First, Team When Needed**：简单任务单 Agent 完成，复杂任务由 DevOps Leader 动态组建 AgentTeam。
- **MaaS decoupling**：MoMA 是比赛版默认 MaaS Provider，模型智能层通过 Provider + Routing Policy 解耦，便于未来接入其他 MaaS。
- **Runtime decoupling**：OpenJiuwen Agent Core 是 SDK / Runtime 依赖，不 fork、不复制其源码；DevOps 领域层自主实现。
- **Evaluation-driven**：任何模型路由、AgentTeam 与 Self-Evolving 改动必须通过 DevOpsBench 验证。
- **Controlled evolution**：进化对象先限定为 Prompt、Skill、Routing Policy、Team Pattern 与 Tool Strategy，候选版本必须评测、审批、可回滚。

## Documentation

产品与技术决策基线位于 [PRD/](./PRD/)。

当前阶段：**Product Definition & Architecture Definition**。在 PRD v0.1 冻结前，不进入大规模业务实现。
