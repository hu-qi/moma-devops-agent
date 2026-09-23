# 05 — MoMA & MaaS Routing

## 1. Goal

MoMA 不是一个固定模型 Endpoint，而是比赛版默认的模型能力与调度平台。

DevOpsPilot 自主负责“这个任务需要什么能力”，MaaS Provider 负责“平台上如何得到对应模型服务”。

## 2. Two-level Routing

```text
Task
 ↓
TaskProfiler
 ↓
ModelCapabilityProfile
 ↓
DevOps RoutingPolicy
 ↓
MaaSProvider
 ↓
MoMA
 ↓
Concrete Model / Route
```

## 3. TaskProfile

建议字段：

```text
task_type
complexity
risk_level
context_size
latency_budget
cost_budget
reasoning_requirement
coding_requirement
review_requirement
structured_output_requirement
privacy_level
```

## 4. Model Capability Profiles

V1 先定义能力档，不把具体模型写死：

### FAST
分类、摘要、PR/Commit 描述、低风险转换。

### REASONING
规划、复杂 Bug、CI RCA、架构推理。

### CODING
代码理解、实现、重构、测试生成。

### REVIEW
独立 Code Review、安全与质量审查。

### JUDGE
Benchmark 评测、候选策略比较、结果裁决。

## 5. MaaS Provider Contract

概念接口：

```python
class MaaSProvider:
    async def invoke(self, request): ...
    async def stream(self, request): ...
    async def list_models(self): ...
    async def get_capabilities(self): ...
```

Provider 不负责 DevOps 任务分类。

## 6. Providers

比赛版：
- MoMAProvider

未来：
- HuaweiCloudProvider
- AlibabaCloudProvider
- VolcengineProvider
- TencentCloudProvider
- OpenAICompatibleProvider

## 7. Cross-model Verification

高风险任务避免同模型自证。

例如：

```text
Coding Model → Patch
                   ↓
Reviewer Model → Independent Review
                   ↓
Rule / Test Gate → Verify
```

发布风险可使用：
- reasoning model
- reviewer model
- deterministic rule gate

联合判断。

## 8. Routing Metrics

每次模型调用必须记录：
- selected profile
- provider
- model
- route reason
- latency
- input/output tokens
- estimated cost
- success/failure
- retry/fallback
- downstream task result

这些数据既服务 DevOpsBench，也服务 Routing Policy 自进化。

## 9. Fallback

Routing Policy 必须支持：
- model unavailable
- quota exceeded
- latency timeout
- context overflow
- malformed output
- capability mismatch

Fallback 本身也进入评测。

## 10. Competition Evidence

最终必须用实验回答：

> 相比固定模型，MoMA + DevOpsPilot Routing 是否提升任务成功率、降低延迟/成本，或提高稳定性？

这是比赛版 Model Intelligence 的关键证据。
