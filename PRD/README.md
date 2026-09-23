# PRD

本目录是 DevOpsPilot 的产品与技术决策唯一事实源（Source of Truth）。

## Baseline v0.1

1. [00-decisions.md](./00-decisions.md) — 已冻结的产品与架构决策
2. [01-product-definition.md](./01-product-definition.md) — 产品定位、目标用户与价值
3. [02-v1-scope.md](./02-v1-scope.md) — V1 功能边界与成功标准
4. [03-architecture.md](./03-architecture.md) — 总体技术架构
5. [04-agent-team.md](./04-agent-team.md) — 动态 AgentTeam 设计
6. [05-moma-and-maas-routing.md](./05-moma-and-maas-routing.md) — MoMA 与 MaaS 路由
7. [06-self-evolving-rsi.md](./06-self-evolving-rsi.md) — Self-Evolving / RSI
8. [07-scm-and-devops-provider.md](./07-scm-and-devops-provider.md) — SCM / DevOps Provider
9. [08-industry-engineering-packs.md](./08-industry-engineering-packs.md) — 行业工程包
10. [09-devopsbench.md](./09-devopsbench.md) — DevOpsBench 评测体系
11. [10-demo-plan.md](./10-demo-plan.md) — 比赛 Demo 主线

## Working Rule

任何实现性代码进入仓库前，必须能够追溯到本目录中的产品目标、架构约束或评测目标。重大方向调整先修改 PRD，再进入实现。
