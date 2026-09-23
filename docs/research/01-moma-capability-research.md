# 01 — MoMA Capability Research

Date: 2026-09-23  
Status: **Round 1 / static research completed; credentialed API spike pending**

## 1. Executive Conclusion

MoMA 与 DevOpsPilot 的产品方向高度匹配：公开资料确认其定位为多模型聚合与调度平台，支持“一次接入、智能优选”，并强调模型聚合、智能路由、高可用与 Token 经营。

但当前公开网络上没有找到足够完整、可权威核验的 MoMA 开发者 API Reference。因此必须严格区分：

- **平台级能力已确认**
- **API 级能力有公开线索但尚未通过官方文档/实测确认**
- **DevOpsPilot 必须 live spike 验证的能力**

## 2. Evidence Levels

### A — 官方公开信息确认

中国移动 2026 年半年度报告明确：
- MoMA 为移动模型服务平台（Mixture of Models and Agents）。
- 平台升级后强调“一次接入、智能优选、普惠可用、安全可信”。
- 建设 MoMA 专属算力池。
- MoMA 位于模型/算力调度体系核心。

Source:
- China Mobile 2026 Interim Report: https://static.cninfo.com.cn/finalpage/2026-08-14/1225472195.PDF

中国移动此前公开报告还描述 MoMA 为“多模型和智能体聚合服务引擎”，面向大小模型、不同模态、工具链与智能体进行自主选择和匹配。

Source:
- China Mobile 2025 Interim Report: https://static.cninfo.com.cn/finalpage/2025-08-07/1224425847.PDF

### B — 多个公开报道交叉确认

公开报道一致描述：
- 接入 300+ 主流模型。
- 包括九天、DeepSeek、Qwen、GLM 等。
- 智能路由支持成本优先 / 效果优先 / 均衡优先。
- 出现超时、限流或故障时支持自动切换。
- 结合缓存、上下文复用等方式降低 Token 成本。

References:
- https://www.citmt.cn/news/202605/123173.html
- https://finance.sina.com.cn/enterprise/central/2026-07-31/doc-inikstfm1319701.shtml
- https://ue.aliyun.com/news/20260522

### C — 第三方接入资料，必须实测

第三方渠道给出了 OpenAI-compatible Chat Completions 调用方式，并出现：
- OpenAI-compatible gateway
- `/v1/chat/completions`
- Bearer API Key
- `stream`
- 模型名带厂商前缀

但该类页面不是 MoMA 官方开发者文档，因此 endpoint、版本、参数不可写死进 Core。

Reference:
- https://qelkj.com/pc/cloud/cmcc/moma.html

## 3. Capability Matrix

| Capability | Status | Evidence / Action |
|---|---|---|
| Multi-model aggregation | CONFIRMED | Official/public reports |
| DeepSeek / Qwen / GLM availability | CONFIRMED at platform level | Public ecosystem reports |
| Intelligent model routing | CONFIRMED at platform level | Official/public reports |
| Cost/effect/balanced routing policy | HIGH CONFIDENCE | Multiple public reports |
| Automatic failover | HIGH CONFIDENCE | Multiple public reports |
| OpenAI-compatible Chat Completions | PROBABLE | Third-party API example; live verify |
| Streaming | PROBABLE | Third-party API example; live verify |
| Usage/token accounting | EXPECTED | Must inspect live response |
| Tool / Function Calling | UNKNOWN | Live verify |
| Structured Output / JSON Schema | UNKNOWN | Live verify |
| Reasoning content field | UNKNOWN | Live verify per model |
| List-models API | UNKNOWN | Console/API verify |
| Router API parameters | UNKNOWN | Console/API verify |
| Selected-model metadata after routing | UNKNOWN | Live verify |
| Route reason / confidence | UNKNOWN | Live verify |
| Context reuse exposed to application | UNKNOWN | Platform capability != public API |
| Prompt caching usage metrics | UNKNOWN | Live verify |
| Rate limit headers / quota API | UNKNOWN | Live verify |
| Embedding / rerank APIs | UNKNOWN | Console/API verify |
| Vision / multimodal request format | PLATFORM CONFIRMED, API UNKNOWN | Live verify |

## 4. DevOpsPilot Integration Strategy

Do not bind DevOpsPilot to one assumed MoMA routing API.

Support two modes behind `MoMAProvider`.

### Mode A — Managed Routing

If MoMA exposes programmable intelligent-routing parameters:

```text
TaskProfile
  ↓
DevOpsPilot RoutingPolicy
  ↓
Capability requirement + route objective
  ↓
MoMA Smart Router
  ↓
Selected model
```

DevOpsPilot controls:
- task classification
- required capability
- risk
- cost/latency preference

MoMA controls:
- concrete model selection
- failover
- infrastructure routing

### Mode B — Direct Model

If MoMA intelligent routing is not exposed through public API:

```text
TaskProfile
  ↓
DevOpsPilot RoutingPolicy
  ↓
Model alias / concrete model
  ↓
MoMA unified model endpoint
```

The product remains valid. MoMA is still the default MaaS model pool; our RoutingPolicy owns model selection.

## 5. Required Live Spikes

### M1 — Basic Chat
Verify:
- base URL
- auth
- model ID
- response shape
- usage

### M2 — Streaming
Verify:
- SSE/chunk format
- first-token latency
- finish_reason
- usage placement

### M3 — Tool Calling
Verify:
- OpenAI tools schema compatibility
- tool_calls output shape
- parallel tool calls
- streaming tool calls

### M4 — Structured Output
Verify:
- JSON mode
- JSON Schema if available
- invalid output behavior

### M5 — Intelligent Routing
Verify:
- how route mode is selected
- route strategy values
- whether chosen model is returned
- failover metadata
- route observability

### M6 — Reasoning/Coding Models
At least test:
- one fast model
- one reasoning model
- one coding-capable model
- one reviewer/judge candidate

## 6. Decision

**Proceed with MoMA as the competition-default MaaS Provider.**

Do not freeze exact endpoint or router parameter names until credentialed API verification completes.

The DevOpsPilot `MaaSProvider` abstraction remains mandatory.
