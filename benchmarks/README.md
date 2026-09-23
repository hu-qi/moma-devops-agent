# DevOpsBench

DevOpsPilot 的可重复软件工程评测基准。

## V0.1

首批三类 Case：

- coding
- code-review
- ci-debug

## Layout

```text
benchmarks/
├── schemas/
│   ├── benchmark-case.schema.json
│   └── evaluation-result.schema.json
├── devopsbench/
│   └── runner.py
└── cases/
    ├── coding-python-off-by-one/
    ├── review-python-sql-injection/
    └── ci-python-wrong-working-directory/
```

## Case Lifecycle

DevOpsBench 明确区分“初始故障态”和“候选结果态”。

```text
fixture
  ↓
precondition
  ↓ 证明问题真实存在
Agent / Candidate
  ↓
oracle
  ↓ 证明任务真的被解决
EvaluationResult
```

不能把初始 fixture 的预期失败误记为 Agent 评测失败。

## Validate Fixtures

验证所有公开 case 的初始状态确实满足预期故障条件：

```bash
python benchmarks/devopsbench/runner.py validate-fixtures
```

该命令不调用任何模型，可在 CI 中稳定运行。

## Evaluate Candidate

对于 command-based oracle，Agent Adapter 准备好候选 workspace 后调用：

```bash
python benchmarks/devopsbench/runner.py evaluate \
  --case coding.python.off_by_one.001 \
  --workspace /path/to/candidate \
  --variant A0-fixed-single
```

Code Review 的 `structured-review` oracle 将由下一阶段的 Agent-result adapter 评测，deterministic runner 不会用字符串猜测代替正式 evaluator。

## Evaluation Strategy

优先级：

1. deterministic executable oracle
2. static rule / linter oracle
3. structured human rubric
4. LLM judge only when unavoidable

后续所有 MoMA Routing、AgentTeam 和 RSI 实验都必须回写为同一 `EvaluationResult` 契约，才能做 A0/A1/A2/A3 对照。
