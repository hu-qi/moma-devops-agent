# DevOpsBench 案例库扩充规划（C20）

对应任务：`docs/competition/TODO.md` C20。基线：2026-09-29。

## 1. 现状盘点

现有 **9 例**（`benchmarks/cases/`），三类各 3 例，schema 已含 `provenance`（source/license/notes）、`oracle`、`budget`、`constraints`：

| 类别 | 案例 | 许可 | 来源 |
|---|---|---|---|
| coding | calculator / json-parser / off-by-one | CC0-1.0 | 合成 fixture |
| code-review | clean-refactor / sql-injection / unmasked-pii | CC0-1.0 | 合成 fixture |
| ci-debug | env-mismatch / missing-dependency / wrong-cwd | CC0-1.0 | 合成 fixture |

**缺口**：① 数量 9 → 20–30；② 无 holdout 划分；③ 无"允许改动边界"（allowed_paths）的统一复审记录。

## 2. 扩充规划（目标 24 例：每类 8）

新增 15 例全部保持合成 fixture（来源可控、许可干净、oracle 可确定性重算），延续 `DevOpsPilot synthetic fixture` + CC0-1.0 provenance，不引入来源不明的外部数据。

| 类别 | 新增案例（规划 id） | oracle 类型 |
|---|---|---|
| coding (5) | string-format-injection / mutable-default-arg / timezone-naive-datetime / resource-leak-context-manager / exception-swallowing | command-exit |
| code-review (5) | hardcoded-secret / path-traversal / race-condition-shared-state / unsafe-deserialization / missing-authz-check | structured-review |
| ci-debug (5) | flaky-test-order-dependence / port-already-in-use / encoding-mismatch-utf8 / cache-poisoning-artifact / workflow-permission-too-broad | command-exit（verify 脚本） |

每例必须填写：`constraints.allowed_paths/forbidden_paths`（允许改动边界）、`budget`、`risk`、`tags`、完整 `provenance`。

## 3. Holdout 划分

在 `case.json` 增加 `"holdout": false`（默认，可参与对照评测）或 `true`（留作盲测，不参与调参/候选优化）：

- 每类保留 **2 例 holdout**（共 6），其余 18 例可公开评测。
- holdout 划分固定写入 case.json，评测报告须分别统计 visible/holdout 两组，禁止用 holdout 结果调优。
- `runner.py` 需支持 `--include-holdout` 显式开关（默认排除）。

## 4. 执行顺序

1. 在 case.json 补 `holdout` 字段（9 例现状先行）。
2. 按 §2 逐例新增 fixture + case.json（每例附 precondition 反例验证：修复前必失败、修复后必通过）。
3. `runner.py validate-fixtures` 全量通过后纳入 40 项离线套件。
