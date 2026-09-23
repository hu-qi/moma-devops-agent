# MoMA Credentials for GitHub Actions

DevOpsPilot 不在源码、Prompt、Benchmark 或实验日志中保存 MoMA 密钥。

## Repository Secret

打开：

`Settings → Secrets and variables → Actions → Secrets`

创建：

- `MOMA_API_KEY`

API Key 必须使用 **Secret**，不要使用普通 Variable。

## Repository Variables

打开：

`Settings → Secrets and variables → Actions → Variables`

创建：

- `MOMA_API_BASE`
- `MOMA_MODEL`

可选：

- `MOMA_REASONING_MODEL`
- `MOMA_CODING_MODEL`
- `MOMA_REVIEW_MODEL`

如果角色模型未配置，实验应回退到 `MOMA_MODEL`。

## OpenJiuwen Install Source

可选 Variable：

- `OPENJIUWEN_INSTALL_SPEC`

当前技术摸底建议值：

```text
openjiuwen[observability,sqlite] @ git+https://github.com/openJiuwen-ai/agent-core.git@release/v0.1.19
```

注意：截至 2026-09-23，`release/v0.1.19` 分支已经包含并可运行 RSI 公共能力，但其 Python 包 metadata 在 CI 实测中仍报告 `0.1.18`。因此 DevOpsPilot 同时记录 **source ref** 与 **installed package metadata**，不把二者混为一谈。

## Verified CI Evidence

GitHub Actions `Technical Spike` run `35871041631` 已成功验证：

- AgentTeam public surface 可导入；
- `TeamAgentSpec.evolution_enabled` 存在且默认开启；
- `openjiuwen.rsi` 可导入；
- `AutoHarnessOrchestrator` 可导入；
- `TeamEvaluator` 可导入；
- `MemberOptimizer` 可导入；
- `ProgramArtifactProvider` 可导入；
- `SingleHarnessIterativeOptimizationOrchestrator` 可导入。

MoMA live job 尚需配置上述 Secret / Variables 后手动触发。

## Security Rules

- 不把 `MOMA_API_KEY` 提交 Git。
- 不在 workflow 中 `echo` Secret。
- 不把 Secret 写进 Actions Artifact。
- 不把凭据传给 LLM Prompt。
- Tool/Agent 只获得完成任务所需的最小权限。
- 如密钥出现在日志或 Git 历史中，立即轮换。
