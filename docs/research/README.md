# Technical Research

本目录记录 DevOpsPilot 的技术摸底、Spike、能力矩阵、实验与架构结论。

## Completed / Active

1. [01-moma-capability-research.md](./01-moma-capability-research.md) — MoMA 平台与 API 能力边界
2. [02-openjiuwen-runtime-research.md](./02-openjiuwen-runtime-research.md) — OpenJiuwen Runtime / 0.1.19 line
3. [03-moma-openjiuwen-integration-spike.md](./03-moma-openjiuwen-integration-spike.md) — MoMA × OpenJiuwen live spike 计划
4. [04-agentteam-rsi-spike.md](./04-agentteam-rsi-spike.md) — AgentTeam + RSI 联动摸底
5. [04-agentteam-runtime-research.md](./04-agentteam-runtime-research.md) — AgentTeam Runtime 边界
6. [05-rsi-evolution-research.md](./05-rsi-evolution-research.md) — Self-Evolving / RSI 研究
7. [05-devopsbench-v0.1.md](./05-devopsbench-v0.1.md) — DevOpsBench v0.1
8. [06-devopsbench-v0.1-contract.md](./06-devopsbench-v0.1-contract.md) — Benchmark Contract
9. [07-core-contracts.md](./07-core-contracts.md) — DevOpsPilot Core Contracts
10. [08-scm-capability-matrix.md](./08-scm-capability-matrix.md) — GitHub / GitCode / AtomGit / Gitee / CNB / GitLink 能力矩阵

## Evidence Rule

所有结论必须标识为以下类别之一：

- **CI / live verified** — 已由真实程序或 CI 运行验证
- **Official docs confirmed** — 官方文档确认
- **High-confidence inference** — 多个可靠来源支持，但尚未实测
- **Pending** — 必须通过账号、凭据或真实环境验证

不得把平台宣传能力直接等同于 API 已验证能力。

## Decision Flow

```text
Research / Spike
      ↓
Evidence
      ↓
Core Contract / PRD Decision
      ↓
Implementation
      ↓
DevOpsBench
```

重大技术决策回写 `PRD/00-decisions.md`；实现代码不得绕过已冻结的 Core Contracts。
