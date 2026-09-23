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

**Technical Exploration → Reference Adapters & Live Capability Verification**

## OpenJiuwen 0.1.19

GitHub Actions 已从：

```text
openJiuwen-ai/agent-core@release/v0.1.19
```

真实安装并运行。

解析 commit：

```text
6f3a33fbb93aece65105c477c573057fead0e8dd
```

Runtime Surface CI 已确认：
- TeamAgentSpec
- DeepAgent / create_deep_agent
- TeamEvaluator
- MemberOptimizer
- ProgramArtifactProvider
- SingleHarnessIterativeOptimizationOrchestrator
- create_auto_harness_orchestrator

AgentTeam 与 RSI 均为 runtime-verified capability。

## MoMA — Basic Live Path VERIFIED

Workflow:

```text
MoMA Live Smoke
run 35876800666
result: success
```

实际链路：

```text
MoMA
 ↓
OpenAI-compatible endpoint
 ↓
OpenJiuwen Model.invoke
 ↓
DeepAgent.invoke
 ↓
success
```

当前 bootstrap model：
`deepseek-v4-flash-0731`

实测确认：
- endpoint/auth 配置有效
- Model.invoke 成功
- DeepAgent.invoke 成功
- usage token 可读
- reasoning content 可读
- response model 可读
- TTFT / generation / queue / TPS 等 provider metrics 可读

当前 bootstrap model 不支持 image input；OpenJiuwen 自动 capability probe 正确识别并降级。该结论仅针对当前模型，不代表 MoMA 平台没有多模态模型。

下一轮 workflow：
`MoMA Capability Spikes`

目标：
- Streaming
- Tool Calling
- Dynamic AgentTeam
- RSI Runtime Injection

## MoMA Model Configuration

新增：

```text
configs/models/moma.yaml
```

`MOMA_MODEL` 明确定义为 bootstrap/default model。

正式模型策略仍然是：

```text
TaskProfile
 ↓
FAST / REASONING / CODING / REVIEW / JUDGE
 ↓
RoutingPolicy
 ↓
MoMA Provider
```

## DevOpsBench

DevOpsBench CI 已连续成功。

当前支持：
- deterministic fixture preconditions
- candidate evaluation evidence
- solution oracle semantics
- baseline/candidate lifecycle

## Provider Contracts

Core Provider Contract workflow：**success**

当前标准契约：
- MaaSProvider
- SCMProvider
- CIProvider
- ReviewState / ReviewRef
- CICapability
- CIArtifactRef

SCM 与 CI 保持解耦。

## GitHub Reference Adapter — VERIFIED

新增：
- `src/devopspilot/adapters/github/client.py`
- `src/devopspilot/adapters/github/scm.py`
- `src/devopspilot/adapters/github/ci.py`

覆盖：
- Repository
- Issue
- PR create/read
- Comment
- Review
- Webhook normalization
- HMAC SHA-256 webhook verification
- Actions run
- job logs
- retry failed jobs
- trigger/cancel
- artifacts

`GitHub Reference Adapter` workflow：**success**

该 Adapter 现在是后续国产 Provider 的 reference implementation。

## CNB — Domestic Provider Spike

官方 CNB CLI v1.16.13 已通过 GitHub Actions 安装与命令面验证。

已观察：
- issues module: 33 tools
- pulls module: 34 tools
- pull review tools
- `pulls get-ci-logs`
- `pulls get-ci-timing`
- build start/status/logs/stop

这验证 CNB 具备实现完整 SCM + CI Provider 的能力面。

新增：
- `src/devopspilot/adapters/cnb/client.py`
- `docs/research/10-cnb-adapter-strategy.md`

当前先实现 CLI transport；在 detailed CLI help 验证参数/输出后，再实现 `CNBSCMProvider` 和 `CNBCIProvider`。

## Next

1. 完成 MoMA Streaming / Tool Calling / AgentTeam / RSI live spikes。
2. 完成 CNB CLI detailed surface。
3. 实现 CNB SCM/CI provider mapping。
4. 把 GitHub + CNB 都接入同一 provider contract suite。
5. 进入第一个跨平台 Issue → PR → CI 标准化闭环。
