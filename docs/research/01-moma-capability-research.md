# 01 — MoMA Capability Research

Date: 2026-09-23  
Status: **Live API baseline verified; advanced capability spikes in progress**

## 1. Executive Conclusion

MoMA 已经通过 DevOpsPilot 的真实 CI 验证，可作为 OpenJiuwen 0.1.19 的模型数据面。

已实测链路：

```text
MoMA OpenAI-compatible endpoint
        ↓
OpenJiuwen Model.invoke
        ↓
DeepAgent.invoke
        ↓
successful response
```

当前 bootstrap 模型：
- configured id: `deepseek-v4-flash-0731`
- provider response model: `deepseek-v4-flash`

`MOMA_MODEL` 仅作为 bootstrap/default model，不代表最终多模型路由设计。

## 2. Evidence Levels

### A — CI / live verified

GitHub Actions workflow:

```text
MoMA Live Smoke
run: 35876800666
result: success
```

已确认：

- GitHub Actions Secret/Variables 配置有效。
- MoMA 接受 OpenAI-compatible Chat Completions 请求。
- OpenJiuwen `ModelClientConfig(client_provider="OpenAI", endpoint_profile="openai_compatible")` 可直接调用 MoMA。
- `Model.invoke()` 成功。
- `DeepAgent.invoke()` 成功。
- response usage 包含 input/output/total token。
- response 暴露 reasoning content。
- provider response 暴露 concrete response model。
- 服务响应包含性能指标，例如 time-to-first-token、generation time、queue time、tokens/sec。
- OpenJiuwen checkpoint/session 在该模型链路上正常完成。

Basic probe output：

```text
MOMA_OPENJIUWEN_OK
```

DeepAgent output：

```json
{"status":"ok","runtime":"openjiuwen"}
```

### B — 官方公开信息确认

中国移动公开材料确认 MoMA 是移动模型服务平台（Mixture of Models and Agents），强调：
- 一次接入
- 智能优选
- 多模型聚合
- 模型/算力调度
- 高可用和安全可信

Sources:
- China Mobile 2026 Interim Report
- China Mobile 2025 Interim Report

### C — 平台能力确认但 API 细节待验证

公开资料与生态报道支持：
- 300+ 主流模型
- DeepSeek / Qwen / GLM 等模型池
- 成本优先 / 效果优先 / 均衡优先等智能路由思路
- 故障切换
- 上下文/缓存相关 Token 优化

这些不能直接等同于当前公开 API 参数已经确认。

## 3. Capability Matrix

| Capability | Status | Evidence / Action |
|---|---|---|
| Multi-model aggregation | CONFIRMED platform | Official/public reports |
| DeepSeek family availability | LIVE VERIFIED | Current bootstrap model |
| Qwen / GLM availability | CONFIRMED platform | Model pool research; later enumerate |
| OpenAI-compatible Chat | **LIVE VERIFIED** | MoMA Live Smoke |
| Basic auth / endpoint | **LIVE VERIFIED** | GitHub Actions |
| OpenJiuwen Model.invoke | **LIVE VERIFIED** | CI |
| OpenJiuwen DeepAgent.invoke | **LIVE VERIFIED** | CI |
| Usage/token accounting | **LIVE VERIFIED** | input/output/total/cache fields observed |
| Reasoning content | **LIVE VERIFIED for current model** | response contains reasoning |
| Concrete response model metadata | **LIVE VERIFIED** | configured vs response model observed |
| Provider performance metrics | **LIVE VERIFIED** | TTFT / generation / queue / TPS observed |
| Streaming | SPIKE RUNNING | `MoMA Capability Spikes` |
| Tool / Function Calling | SPIKE RUNNING | `MoMA Capability Spikes` |
| Dynamic AgentTeam on MoMA | SPIKE RUNNING | `MoMA Capability Spikes` |
| OpenJiuwen RSI model injection | SPIKE RUNNING | `MoMA Capability Spikes` |
| Structured Output / JSON Schema | UNKNOWN | next probe |
| Intelligent-routing request parameters | UNKNOWN | requires official/live route probe |
| Route reason / confidence | UNKNOWN | live verify |
| Automatic failover metadata | UNKNOWN | live verify |
| List-models API | UNKNOWN | console/API verify |
| Rate limit / quota API | UNKNOWN | live verify |
| Embedding / rerank | UNKNOWN | console/API verify |

## 4. Multimodal Finding

OpenJiuwen automatically probed image capability during the DeepAgent smoke.

The configured `deepseek-v4-flash-0731` endpoint returned HTTP 400 indicating that this **specific model is not multimodal**.

Interpretation:

```text
current bootstrap model != multimodal
```

Do **not** interpret this as:

```text
MoMA platform has no multimodal models
```

The Runtime correctly detected unsupported image input and continued with text capability.

For normal DevOpsPilot coding tasks, explicitly disabling unnecessary image probing is preferable unless the selected capability profile requires vision.

## 5. Observability Finding

The live response currently exposes enough information to seed DevOpsPilot routing telemetry:

```text
configured model
response model
input tokens
output tokens
total tokens
cache tokens
reasoning content
finish reason
TTFT
queue time
generation time
tokens/sec
```

These should later project into the canonical DevOpsPilot `Trajectory`, not remain only in OpenJiuwen logs.

## 6. DevOpsPilot Integration Strategy

Maintain two possible MoMA modes.

### Direct Model Mode — verified

```text
TaskProfile
  ↓
RoutingPolicy
  ↓
concrete model / bootstrap model
  ↓
MoMA OpenAI-compatible endpoint
```

This path is now technically proven.

### Managed Routing Mode — not yet API-verified

```text
TaskProfile
  ↓
capability + route objective
  ↓
MoMA smart routing
  ↓
concrete model
```

Do not freeze parameter names until a real route request is verified.

## 7. Next Live Spikes

### M2 — Streaming
Validate chunking, finish reason and usage placement.

### M3 — Tool Calling
Validate OpenAI tools schema and `tool_calls` parsing.

### M4 — Dynamic AgentTeam
Validate Leader → dynamically spawned Coding/Review members using MoMA.

### M5 — RSI Runtime Injection
Validate a MoMA-backed Model can be injected into OpenJiuwen RSI orchestration.

### M6 — Structured Output
Validate JSON mode / JSON Schema if supported.

### M7 — Managed Routing
Validate the actual MoMA smart-routing API and returned routing metadata.

## 8. Decision

**MoMA is now a technically verified default MaaS Provider for DevOpsPilot's basic model/DeepAgent path.**

The next risk is no longer “can MoMA connect to OpenJiuwen”; it is:

> which advanced capabilities can be relied on for autonomous DevOps execution, and which belong in DevOpsPilot's own control plane?
