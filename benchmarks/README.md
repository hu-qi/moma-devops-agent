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
├── devopsbench/
│   └── runner.py
└── cases/
    ├── coding-python-off-by-one/
    ├── review-python-sql-injection/
    └── ci-python-wrong-working-directory/
```

## Case Contract

每个 Case 至少包含：
- `case.json`
- `fixture/`
- deterministic oracle 或 reviewer oracle

## Run

```bash
python benchmarks/devopsbench/runner.py
```

Runner v0.1 先验证 case 元数据与 deterministic command oracle。Agent execution adapter 在下一阶段接入。
