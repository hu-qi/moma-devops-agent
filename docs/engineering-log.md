# DevOpsPilot Engineering Log

## 2026-09-23

### Product Baseline
已冻结 PRD v0.1：
- DevOpsPilot —— MoMA 驱动的自进化多智能体研发交付系统
- OpenJiuwen Agent Core 作为核心 SDK / Runtime 依赖
- MoMA 作为比赛版默认 MaaS Provider
- Dynamic AgentTeam
- Self-Evolving / RSI
- DevOpsBench
- Multi-SCM Provider
- Industry Engineering Packs

### Current Phase
**Technical Exploration / Spike**

### Round 1 — MoMA × OpenJiuwen

#### Completed
- 建立研发留痕与技术调研目录。
- 完成 MoMA 平台能力静态调研。
- 明确区分平台已确认能力、第三方 API 线索和必须 live verify 的接口行为。
- 完成 OpenJiuwen 0.1.18 Runtime / DeepAgent / AgentTeam / Self-Evolving 静态 API 验证。
- 确认 OpenJiuwen 存在 generic `openai_compatible` endpoint profile。
- 确认 DeepAgent 主工厂可注入 model / tools / MCP / subagents / rails / workspace / skills / planning。
- 准备 MoMA × OpenJiuwen 最小 PoC。

#### Key Finding
静态分析支持以下集成路径：

```text
MoMA OpenAI-compatible endpoint
          ↓
OpenJiuwen Model
          ↓
DeepAgent
          ↓
DevOpsPilot Orchestration
```

目前没有证据表明需要 fork 或修改 OpenJiuwen Runtime。

#### Pending Live Verification
需要 MoMA 合法凭据后验证：
- basic chat
- streaming
- tool calling
- structured output
- intelligent routing parameters/metadata
- AgentTeam multi-model execution

凭据不得提交仓库。

### Next
继续验证：
1. AgentTeam 动态组队与隔离边界。
2. Skill / Team Skill Self-Evolving 与 DevOpsPilot Evolution Contract 的映射。
3. DevOpsBench v0.1 Contract 与首批 deterministic fixtures。
