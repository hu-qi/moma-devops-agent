# 00 — Decisions

Status: **Frozen for PRD v0.1**

## D-001 Product

产品名称：**DevOpsPilot**

副标题：**MoMA 驱动的自进化多智能体研发交付系统**

DevOpsPilot 不是单一行业业务 Agent，而是面向政务、金融、工业、医疗等行业的软件研发智能底座。

## D-002 Industry Strategy

采用“横向研发交付底座 + 纵向 Industry Engineering Pack”。

Core 不硬编码行业规则；行业差异通过 Pack 提供知识、规范、合规、安全、测试门禁、Agent Team Pattern 与 Benchmark。

## D-003 Runtime

OpenJiuwen Agent Core 是核心 **SDK / Runtime 依赖**。

- 不 fork agent-core 作为作品代码。
- 不复制其实现。
- DevOps Domain Layer、Skills、Tools、Routing、Benchmark、Evolution Policy 自主实现。

## D-004 AgentTeam

采用 **Single Agent First, Team When Needed**。

固定核心角色只有 DevOps Leader；Coding、Review、CI、Research、Release 等 Specialist 按任务动态创建。

## D-005 Self-Evolving / RSI

从 V1 架构开始支持。

V1 可进化对象：
- Prompt
- Skill
- Routing Policy
- Team Pattern
- Tool Strategy

候选版本不得自动覆盖生产版本，必须经过 Benchmark、Regression Gate、Human Approval 和版本化发布。

## D-006 Model Intelligence

采用两级路由：

1. DevOpsPilot 自主实现 TaskProfile → ModelCapabilityProfile / Routing Policy。
2. MaaS Provider 承担具体模型服务与平台侧调度。

比赛版默认 MaaS Provider 为 **移动云 MoMA**，但架构不绑定单一云。

## D-007 SCM

SCM 必须 Provider 化，不以 GitHub 为 Core。

首批目标平台：
- GitHub
- GitCode
- AtomGit
- Gitee
- CNB
- GitLink

未来可扩展 GitLab、CodeArts Repo 等。

## D-008 Evaluation

必须建设独立的 **DevOpsBench**。

至少比较：
- 固定模型 + 单 Agent
- MoMA + 单 Agent
- MoMA + AgentTeam
- MoMA + AgentTeam + Self-Evolving

所有重要能力必须有可量化收益证据。

## D-009 Demo

Demo 展示真实研发交付闭环，而不是功能菜单。

核心故事：Issue → Plan → Coding → Review → PR/MR → CI → Debug → Verify → Trajectory → Evolution Candidate。

## D-010 Originality

原 devops-bot 仅作为需求与产品经验来源，不复制其业务实现到比赛仓库。

新仓库从产品定义、架构设计和代码实现均独立演进。
