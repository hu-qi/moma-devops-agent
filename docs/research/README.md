# Technical Research

本目录记录 DevOpsPilot 的技术摸底、Spike、能力矩阵、实验与架构结论。

## Completed / Active

1. [01-moma-capability-research.md](./01-moma-capability-research.md) — MoMA API 与 live capability evidence
2. [02-openjiuwen-runtime-research.md](./02-openjiuwen-runtime-research.md) — OpenJiuwen Runtime / release-v0.1.19 line
3. [03-moma-openjiuwen-integration-spike.md](./03-moma-openjiuwen-integration-spike.md) — MoMA × OpenJiuwen integration ladder
4. [04-agentteam-rsi-spike.md](./04-agentteam-rsi-spike.md) — AgentTeam + RSI live verification
5. [04-agentteam-runtime-research.md](./04-agentteam-runtime-research.md) — AgentTeam Runtime boundary
6. [05-rsi-evolution-research.md](./05-rsi-evolution-research.md) — Self-Evolving / RSI research
7. [05-devopsbench-v0.1.md](./05-devopsbench-v0.1.md) — DevOpsBench v0.1
8. [06-devopsbench-v0.1-contract.md](./06-devopsbench-v0.1-contract.md) — Benchmark Contract
9. [07-core-contracts.md](./07-core-contracts.md) — DevOpsPilot Core Contracts
10. [08-scm-capability-matrix.md](./08-scm-capability-matrix.md) — GitHub / GitCode / AtomGit / Gitee / CNB / GitLink
11. [09-moma-model-config.md](./09-moma-model-config.md) — bootstrap model vs capability routing
12. [10-cnb-adapter-strategy.md](./10-cnb-adapter-strategy.md) — CNB adapter transport strategy
13. [11-cnb-openapi-contract-mapping.md](./11-cnb-openapi-contract-mapping.md) — CNB Swagger → DevOpsPilot contracts
14. [12-delivery-loop.md](./12-delivery-loop.md) — provider-neutral delivery loop
15. [13-moma-role-model-matrix.md](./13-moma-role-model-matrix.md) — live model Tool Calling qualification
16. [14-devopsbench-role-model-ablation.md](./14-devopsbench-role-model-ablation.md) — qualified role-model comparison plan/results
17. [15-model-vs-runtime-failure-analysis.md](./15-model-vs-runtime-failure-analysis.md) — model capability vs AgentTeam lifecycle failures
18. [15-openjiuwen-trajectory-bridge.md](./15-openjiuwen-trajectory-bridge.md) — OpenJiuwen runtime evidence → canonical trajectory
19. [16-openjiuwen-agentteam-lifecycle-reproducer.md](./16-openjiuwen-agentteam-lifecycle-reproducer.md) — AgentTeam stream/lifecycle reproducer
20. [16-agentteam-termination-pattern.md](./16-agentteam-termination-pattern.md) — bounded termination strategy
21. [17-full-delivery-pipeline-integration.md](./17-full-delivery-pipeline-integration.md) — execute → publish → change request → CI → verify
22. [18-first-live-github-delivery-e2e.md](./18-first-live-github-delivery-e2e.md) — real Issue → AgentTeam → PR → Actions evidence
23. [19-openjiuwen-skill-evolution-candidate.md](./19-openjiuwen-skill-evolution-candidate.md) — Skill evolution candidate generation
24. [20-delivery-evolution-opportunity-routing.md](./20-delivery-evolution-opportunity-routing.md) — trajectory/opportunity mining
25. [21-team-pattern-swarm-skill-proposal.md](./21-team-pattern-swarm-skill-proposal.md) — repeated AgentTeam timeout → governed Team Pattern proposal
26. [22-governed-swarm-skill-candidate.md](./22-governed-swarm-skill-candidate.md) — proposal approval → sandbox creator → official validator
27. [23-team-pattern-devopsbench-ab.md](./23-team-pattern-devopsbench-ab.md) — baseline vs candidate Team/Swarm Skill evaluation
28. [24-governed-artifact-registry.md](./24-governed-artifact-registry.md) — staged → approved activation → rollback/deactivate
29. [25-autonomous-delivery-control-plane.md](./25-autonomous-delivery-control-plane.md) — control plane ledger, bounded policy, same-branch CI remediation, cross-origin logs
30. [26-industry-engineering-packs.md](./26-industry-engineering-packs.md) — Industry Engineering Packs architecture, contracts, and reference government pack
31. [27-atomgit-reference-adapter.md](./27-atomgit-reference-adapter.md) — AtomGit SCM and CI reference adapter implementation and contract verification

## Current Evolution Boundary

Current implementation status and evidence corrections: [2026-09-26 project assessment](../project-assessment-2026-09-26.md). A local mock smoke, one historical live success, and repeatable V1 acceptance are separate evidence levels.

The real repeated-timeout Team Pattern proposal remains **PENDING_HUMAN**.

Current live candidate-generation and A/B infrastructure uses only a **synthetic approval** to verify the mechanism:

~~~text
real evidence
  → real proposal
  → PENDING_HUMAN   (unchanged)

synthetic approved proposal
  → sandbox candidate
  → official validator
  → DevOpsBench A/B
  → RegressionGate
  → REJECTED or PENDING_HUMAN
~~~

No synthetic approval may be interpreted as approval of the real proposal, and no candidate is allowed to mutate production Skills automatically.

## Evidence Rule

所有结论必须标识为以下类别之一：

- **CI / live verified** — 已由真实程序或 CI 运行验证
- **Official docs confirmed** — 官方文档确认
- **High-confidence inference** — 多个可靠来源支持，但尚未实测
- **Pending** — 必须通过账号、凭据或真实环境验证

不得把平台宣传能力直接等同于 API 已验证能力。

## Decision Flow

~~~text
Research / Spike
      ↓
Evidence
      ↓
Core Contract / PRD Decision
      ↓
Implementation
      ↓
DevOpsBench
      ↓
RegressionGate
      ↓
Human Approval
      ↓
Artifact Registry
~~~

重大技术决策回写 PRD/00-decisions.md；实现代码不得绕过已冻结的 Core Contracts。
