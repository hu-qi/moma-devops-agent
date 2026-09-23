# 01 — Product Definition

## 1. Vision

让 AI 从“辅助完成一个编码动作”升级为“自主推进研发任务直到形成可验证交付结果”。

核心闭环：

```text
Understand → Plan → Develop → Review → Verify → Deliver → Observe → Evolve
```

## 2. Positioning

DevOpsPilot 是面向各行业的软件研发智能底座。

```text
DevOpsPilot Core
      │
      ├── Government Engineering Pack
      ├── Finance Engineering Pack
      ├── Industrial Engineering Pack
      └── Healthcare Engineering Pack
```

它解决的是行业软件“如何更正确、更高效、更可控地开发与交付”，而不是替代行业业务决策本身。

## 3. Target Users

- 软件研发工程师
- Tech Lead / 架构师
- DevOps / SRE
- 测试工程师
- 研发管理者
- 行业软件厂商与数字化团队

## 4. Core Problems

### 4.1 Fragmented context

Issue、代码、文档、CI、发布记录与历史故障分散，AI 很难形成持续工程上下文。

### 4.2 Single-model limitations

编码、推理、Review、日志 RCA 的能力诉求不同，固定模型不能同时兼顾质量、速度与成本。

### 4.3 Tool-chain fragmentation

传统 Coding Agent 往往停在本地代码修改，无法自然进入 PR/MR、CI/CD、发布和故障处理链。

### 4.4 Static agent capability

Prompt、Skill、Routing 和团队协作模式通常是静态配置，真实项目变化后能力会逐渐失配。

### 4.5 Industry engineering constraints

政务、金融、工业、医疗的软件开发具有不同的合规、安全、测试、审计和架构约束，通用 Coding Agent 无法直接覆盖。

## 5. Product Pillars

### Autonomous DevOps

从需求进入系统开始，持续推进研发任务，直到得到可验证的交付结果。

### Dynamic AgentTeam

简单任务单 Agent，复杂任务由 Leader 根据任务动态组建 Specialist Team。

### Multi-Model Intelligence

通过 TaskProfile + Routing Policy + MaaS Provider 使用最适合当前任务的模型。

### Industry Engineering Packs

把行业知识转化为软件工程可执行资产，而不仅是知识库。

### Evaluation-Driven Evolution

真实任务产生 Trajectory；Evolution Engine 产生 Candidate；DevOpsBench 验证收益后才允许晋级。

## 6. Product Formula

```text
DevOpsPilot
=
Software Engineering Intelligence
+ Industry Engineering Packs
+ Project-specific Learning
```

技术上：

```text
DevOpsPilot
=
MoMA Model Intelligence
+ OpenJiuwen Runtime
+ Dynamic AgentTeam
+ DevOps Skills & Tools
+ DevOpsBench
+ Self-Evolving / RSI
```

## 7. North Star

DevOpsPilot 的最终目标不是让开发者“写更多代码”，而是构建一个能够理解软件项目、组织智能体团队、自主推进研发任务，并通过真实交付结果持续进化的 AI 软件工程系统。
