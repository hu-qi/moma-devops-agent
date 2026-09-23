# 06 — Self-Evolving / RSI

## 1. Definition

DevOpsPilot 的 Self-Evolving 定义为：

> 基于真实研发任务的可观测轨迹，对 Agent 能力资产进行受控、可评测、可回滚的持续优化。

不等价于 Agent 任意修改自己的生产代码。

## 2. Evolution Loop

```text
Production / Benchmark Tasks
        ↓
Trajectory Store
        ↓
Success / Failure Mining
        ↓
Evolution Engine
        ↓
Candidate Artifact
        ↓
Sandbox Evaluation
        ↓
DevOpsBench
        ↓
Regression Gate
        ↓
Human Approval
        ↓
Versioned Promotion
        ↓
Observe Again
```

## 3. Evolvable Artifacts

V1：
- Prompt
- Skill
- Routing Policy
- Team Pattern
- Tool Strategy

后续可探索：
- memory extraction policy
- context construction policy
- planner strategy
- verifier strategy
- harness-level strategy

Core Runtime 不允许在 V1 自动修改并上线。

## 4. Artifact Lifecycle

每个 Evolution Artifact 必须包含：

```text
artifact_id
type
base_version
candidate_version
source_trajectories
change_summary
evaluation_dataset
baseline_metrics
candidate_metrics
regressions
approval_state
rollback_target
```

## 5. Trajectory

Trajectory 至少记录：
- task / repo / industry context
- plan
- agent/team topology
- model routing
- tool calls
- intermediate artifacts
- test / CI results
- reviewer findings
- human intervention
- token / latency / cost
- final outcome

## 6. Evolution Triggers

候选来源：
- 重复失败模式
- 用户人工纠正
- CI 反复重试
- Token/Latency 异常
- Reviewer 高频同类缺陷
- 新工具/API 变化
- 成功轨迹中可复用策略
- DevOpsBench 弱项

## 7. Evaluation Gate

Candidate 必须至少满足：
- target benchmark improvement
- no critical regression
- safety / permission tests pass
- deterministic checks pass
- versioned and rollbackable

生产晋级默认需要 Human Approval。

## 8. OpenJiuwen RSI Integration

优先评估并复用 OpenJiuwen Agent Core 的：
- trajectory / agent_evolving
- harness_rsi
- artifact optimization
- evaluator
- skill self-evolution

但 DevOpsPilot 对外保持独立 Evolution Provider / Artifact Contract。

即：

```text
DevOpsPilot Evolution Engine
          ↓
Evolution Provider
      ┌───┴────────┐
      ↓            ↓
OpenJiuwen RSI   Future Engine
```

## 9. V1 Demonstration

V1 Demo 至少展示：

```text
CI Debug Skill v1
   ↓
多次轨迹暴露低效步骤
   ↓
产生 Skill Candidate v2
   ↓
DevOpsBench 离线测试
   ↓
成功率/耗时/Token 至少一项改善
   ↓
等待人工晋级
```

展示重点是“有证据的进化”，不是自动改 Prompt 的噱头。
