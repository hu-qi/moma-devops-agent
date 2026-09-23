# DevOpsPilot Engineering Log

## 2026-09-23

### Product Baseline

PRD v0.1 已冻结：
- DevOpsPilot —— MoMA 驱动的自进化多智能体研发交付系统
- OpenJiuwen Agent Core 作为核心 SDK / Runtime
- MoMA 作为比赛版默认 MaaS Provider
- Dynamic AgentTeam
- Self-Evolving / RSI
- DevOpsBench
- Multi-SCM / CI Provider
- Industry Engineering Packs

### Phase

**Technical Exploration → Contract Hardening**

### OpenJiuwen 0.1.19 line

GitHub Actions 已真实从：

```text
openJiuwen-ai/agent-core@release/v0.1.19
```

安装并运行，解析到 commit：

```text
6f3a33fbb93aece65105c477c573057fead0e8dd
```

`Technical Spike` runtime-surface job 已成功。

CI 实测确认公开运行面包含：
- TeamAgentSpec
- DeepAgent / create_deep_agent
- TeamEvaluator
- MemberOptimizer
- ProgramArtifactProvider
- SingleHarnessIterativeOptimizationOrchestrator
- create_auto_harness_orchestrator

因此 AgentTeam 与 RSI 已从“源码推断”升级为 **CI / runtime surface verified**。

### MoMA

已完成静态兼容分析与最小 PoC。

待用户在 GitHub Actions 配置：
- Variable: `MOMA_API_BASE`
- Variable: `MOMA_MODEL`
- Secret: `MOMA_API_KEY`

然后手动运行 `Technical Spike`，设置 `run_moma_live=true`。

密钥不得进入仓库、日志或聊天。

### DevOpsBench

DevOpsBench workflow 已连续通过，当前已具备：
- deterministic fixture precondition
- candidate evaluation evidence
- solution oracle semantics
- benchmark lifecycle documentation

### Core Contracts

已建立：
- TaskProfile / ModelCapability / RoutingDecision
- MaaSProvider
- SCMProvider
- CIProvider

SCM/CI 能力矩阵研究后进一步加固：
- ReviewState / ReviewRef
- SCM get_change_request / submit_review
- CICapability
- CI trigger / cancel / artifacts

原因：现实平台可能 SCM 完整但 CI API 不完整，二者不得被绑定。

### SCM / CI Research

已完成第一轮公开能力矩阵：

- GitHub：完整参考实现面
- GitCode：SCM + Actions API 完整，国内优先
- AtomGit：SCM + Actions API 完整，需验证流水线账号开通
- CNB：OpenAPI + Repo/Issue/PR + Pipeline/Logs 完整，国内优先
- GitLink：当前 CLI/Agent 面覆盖 SCM + CI/Pipeline，需验证 raw API
- Gitee：SCM 强；公开资料显示 Gitee Go Pipeline API/日志能力仍存在关键缺口

当前 provisional adapter wave：

```text
Wave 1: GitHub → CNB → GitCode
Wave 2: AtomGit → GitLink
Wave 3: Gitee SCM + external/generic CI
```

### Active Validation

- `Core Provider Contract` workflow 已加入，用于无凭据验证 provider-neutral contract。
- 下一步：Contract CI 通过后实现 GitHub reference adapter，并准备 CNB / GitCode credentialed adapter spike。
