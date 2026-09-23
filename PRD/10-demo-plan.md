# 10 — Competition Demo Plan

## 1. Principle

Demo 只讲一个完整故事，不展示功能菜单。

## 2. Main Story

一个真实项目收到 Issue：

```text
1. SCM 收到 Issue
2. DevOps Gateway 标准化事件
3. Leader 构建 Repo / Task Context
4. TaskProfiler 判定复杂度与风险
5. Routing Policy 请求 MoMA 对应模型能力
6. Leader 生成 Plan
7. 动态创建 Coding + Review Agent
8. Coding Agent 修改代码、补测试
9. Review Agent 独立审查
10. 自动创建 PR/MR
11. CI 执行
12. 制造或遇到真实 CI Failure
13. CI Agent 分析日志并 RCA
14. Coding/CI Agent 修复
15. CI 再次通过
16. Leader 最终 Verify
17. 输出 Delivery Report
18. 保存 Trajectory
```

## 3. Evolution Second Act

在同一个 Demo 中展示：

```text
历史 CI Debug Trajectories
       ↓
Evolution Engine
       ↓
发现重复低效模式
       ↓
产生 build-debug Skill Candidate
       ↓
DevOpsBench
       ↓
与 baseline 对比
       ↓
指标改善
       ↓
等待 Human Approval
```

这样 Self-Evolving 有数据、有过程、有边界。

## 4. What the Audience Should See

界面不需要复杂。

必须清楚展示：
- 当前 Task / Plan
- 当前 Agent / Team
- MoMA 路由到的能力/模型
- Tool execution
- Code diff
- Review result
- CI result
- Final delivery result
- Trajectory
- Evolution candidate 与 benchmark delta

## 5. Industry Story

比赛最终版建议把主 Demo 包装成一个真实行业软件任务。

候选：
- 政务：权限/审计/留痕类模块
- 金融：审计日志/敏感数据/幂等业务模块
- 工业：设备/边缘/高可用集成模块
- 医疗：敏感数据与接口审计模块

行业选择在完成数据可得性、Demo 可理解性与规则可信度调研后冻结。

## 6. SCM Demonstration

正式演示只需选一个最稳定的平台跑主链，但架构/PPT 明确展示多 SCM Provider。

建议同时准备一个国产平台适配的录屏或截图作为扩展证明。

## 7. Failure-resilient Demo

比赛现场必须准备：
- live path
- recorded fallback
- deterministic fixture
- fixed repository state
- model/provider fallback
- CI result fallback evidence

但所有展示结果必须来自真实运行，不伪造实验数据。

## 8. PPT Evidence

最终 PPT 至少引用 Demo 产生的：
- architecture trace
- model routing trace
- AgentTeam trace
- code diff
- CI before/after
- DevOpsBench table
- Evolution before/after

让 PPT 由真实系统证据生成，而不是先画概念再找实现。
