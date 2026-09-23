# 02 — V1 Scope

## 1. V1 Goal

跑通一条真实、可验证、可评测的研发交付闭环，而不是堆积功能。

## 2. Required End-to-End Flow

```text
Issue / Task
  ↓
DevOps Leader
  ↓
Context Build
  ↓
Task Plan
  ↓
Model Routing
  ↓
Single Agent or Dynamic AgentTeam
  ↓
Code Change
  ↓
Tests
  ↓
Independent Review
  ↓
PR / MR
  ↓
CI
  ↓
Failure RCA / Fix if needed
  ↓
Final Verification
  ↓
Delivery Report
  ↓
Trajectory
  ↓
Evolution Candidate
```

## 3. V1 Required Capabilities

### Agent

- DevOps Leader
- Coding Specialist
- Review Specialist
- CI Specialist
- Dynamic team creation
- Human approval hook

### Model Intelligence

- TaskProfile
- ModelCapabilityProfile
- Routing Policy
- MoMA Provider
- Latency / token / result metrics

### Engineering Tools

- Repository read/write
- Git
- Issue
- PR/MR
- Shell
- Test
- CI status/log
- Comment / feedback

### SCM

V1 Core 必须支持 Provider 抽象。

实现优先级不要求六个平台同日完成，但接口必须覆盖：
GitHub、GitCode、AtomGit、Gitee、CNB、GitLink。

### Evolution

V1 至少实现：
Trajectory → Failure/Success Analysis → Skill/Prompt Candidate → Offline Eval。

### Evaluation

DevOpsBench v0.1 至少包含：
- Coding
- Code Review
- CI Debug

## 4. V1 Non-Goals

暂不追求：

- 全云厂商自动部署
- 大规模 Kubernetes 自治运维
- 完整企业 IAM / Billing
- 重型 Web 管理后台
- 无审批生产发布
- 自动修改 Runtime 核心代码并上线
- 一开始同时完整实现所有 SCM 的全部 API

## 5. V1 Success Criteria

给定一个真实代码仓和 Issue，系统能够：

1. 正确理解任务与仓库上下文。
2. 形成可解释执行计划。
3. 根据任务选择模型能力档。
4. 在必要时动态组建 AgentTeam。
5. 完成代码修改与测试。
6. 由独立 Reviewer 验证结果。
7. 创建 PR/MR。
8. 获取 CI 结果；失败时完成至少一次自动 RCA / 修复尝试。
9. 输出 Delivery Report。
10. 保存完整 Trajectory。
11. 生成至少一个可离线评测的 Evolution Candidate。

满足以上链路即认为 V1 产品成立。
