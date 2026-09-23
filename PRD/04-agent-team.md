# 04 — Dynamic AgentTeam

## 1. Principle

**Single Agent First, Team When Needed.**

AgentTeam 是复杂任务的执行组织方式，不是默认装饰。

## 2. Fixed Core Role

### DevOps Leader

唯一固定核心 Agent。

职责：
- 理解用户任务与工程上下文
- 生成或校验计划
- 判断是否需要组队
- 选择 Team Pattern
- 分派任务
- 处理冲突与依赖
- 汇总并验证最终结果
- 决定是否需要 Human-in-the-loop

Leader 不承担所有具体编码工作。

## 3. Dynamic Specialist Roles

首批 Specialist：

### Coding Agent
- Codebase 分析
- 实现 / 重构
- 单元测试与必要文档

### Review Agent
- 独立 Review
- 缺陷、风险、可维护性、安全检查
- 不默认复用 Coding Agent 的判断

### CI Agent
- Pipeline 状态分析
- 日志 RCA
- 构建、测试、依赖问题修复

V1.5：
- Research Agent
- Release Agent
- Security Agent
- Domain Specialist

## 4. Complexity Gate

Leader 在执行前生成任务画像。

建议输入：

```text
complexity
risk
parallelism
specialization
uncertainty
expected_steps
repo_scope
external_dependencies
```

简单任务：
```text
Leader → Skill/Tool → Verify
```

复杂任务：
```text
Leader
  ├── Coding Agent
  ├── Review Agent
  └── CI Agent
       ↓
     Leader Verify
```

## 5. Team Pattern

Team Pattern 是版本化资产，而不是硬编码流程。

示例：

### pattern: code-change-with-review
- leader
- coding
- reviewer

### pattern: ci-recovery
- leader
- ci
- coding(optional)

### pattern: complex-feature
- leader
- research(optional)
- coding
- review
- ci

Team Pattern 可进入 Self-Evolving，但必须经 DevOpsBench 验证。

## 6. Collaboration Contracts

成员之间只通过结构化任务与 Artifact 协作。

核心对象：
- Task
- Plan
- Finding
- Patch
- ReviewResult
- CIResult
- VerificationResult

避免依赖不可复现的纯自然语言聊天历史。

## 7. Workspace & Isolation

设计要求：
- Team 共享仓库语义上下文
- 成员拥有独立执行上下文
- 必要时使用独立 worktree / sandbox
- 并行修改需要冲突检测
- 工具权限按角色最小化

## 8. Human-in-the-loop

以下动作默认进入审批：
- 高风险批量代码修改
- 生产部署
- 权限 / 凭据相关变更
- 高风险依赖升级
- Evolution Candidate 晋级生产

## 9. OpenJiuwen Mapping

优先复用 Agent Core 提供的：
- TeamAgentSpec / Team runtime
- DeepAgent
- session / checkpoint
- permissions / HITL
- workspace / member lifecycle

DevOpsPilot 自主实现：
- Complexity Gate
- DevOps Team Pattern
- 角色提示词
- Team verification policy
- Team effectiveness evaluation
