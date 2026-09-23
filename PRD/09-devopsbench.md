# 09 — DevOpsBench

## 1. Goal

DevOpsBench 是 DevOpsPilot 的评测基准，用于回答：

- Agent 是否真正完成任务？
- MoMA 路由是否比固定模型更有效？
- AgentTeam 是否值得？
- Self-Evolving 是否带来真实增益？
- Industry Pack 是否提升行业软件工程质量？

## 2. Benchmark Layers

### DevOpsBench-Core

首批任务：
- issue-understanding
- coding
- code-review
- test-generation
- ci-debug
- dependency-debug
- release-risk

V1 至少完成：
- coding
- code-review
- ci-debug

### DevOpsBench-Industry

后续：
- government
- finance
- industrial
- healthcare

## 3. Benchmark Case Contract

每个 Case 建议包含：

```text
id
category
repository_fixture
task
expected_behavior
allowed_changes
forbidden_changes
tests
hidden_tests
risk_level
industry
scoring
timeout
```

## 4. Metrics

核心：
- Task Success Rate
- First-pass CI Pass Rate
- Bug Fix Success Rate
- Review Finding Precision/Recall（有标注集时）
- RCA Accuracy
- Regression Rate
- Human Intervention Rate
- Average Resolution Time
- Tool Calls
- Model Calls
- Tokens
- Estimated Cost

Evolution：
- Evolution Gain
- Regression Delta
- Promotion Success Rate

## 5. Required Ablation

至少四组：

| Variant | Routing | AgentTeam | Evolution |
|---|---|---|---|
| Baseline | fixed model | no | no |
| A | MoMA | no | no |
| B | MoMA | yes | no |
| DevOpsPilot | MoMA | yes | yes |

如果实验结果显示某能力没有稳定收益，应调整设计，而不是为了 PPT 保留。

## 6. Evaluation Principles

- 尽量使用可执行测试而不是只靠 LLM Judge。
- Judge 与被评模型尽量隔离。
- 记录失败原因，而不仅是总分。
- Benchmark Case 必须版本化。
- 防止 Evolution 对固定测试集过拟合。
- 保留 hidden / holdout cases。

## 7. Dataset Sources

可探索：
- 自建小型故障仓库
- 开源仓库历史 Issue/PR 的可复现实例
- CI failure fixtures
- dependency conflict fixtures
- synthetic cases with deterministic tests

使用外部数据必须记录许可证与来源。

## 8. V1 Target

先做 20–30 个高质量、可重复运行的 Case，比快速堆 200 个低质量题更重要。

V1 的目标是建立评测闭环，不追求“行业榜单”规模。
