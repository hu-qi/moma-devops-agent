# DevOpsPilot 当前效果评估报告

日期：2026-10-07。源码基线：7076541e445a9f2da365b52fce74cf6df3c4ff17。报告仅总结现有实测，未补造A0–A3收益数据。

## 已有结果

| 验证项 | 结果 | 证据性质 | 不可推导的结论 |
|---|---|---|---|
| 完整离线检查 | 41通过，0失败；最新19.65秒 | 受控环境组件回归 | 不是41个业务任务成功 |
| DevOpsBench预置验证 | 24通过，0失败 | 本次运行初始缺陷/oracle契约检查 | 不是Agent修复24题成功 |
| 真实Web交付 | Issue7产生PR8，目标提交CI成功 | GitHub/MoMA Live fixture | 不是完整PRD签收或生产试点 |
| 运行健康 | verified_degraded | AgentTeam超时，发布后补审 | 不能计作干净运行成功 |
| 真实Chat | deepseek-v4.1-flash，290输入/69输出tokens | 一次真实MoMA问答 | 不是广泛准确率测试 |

## 当前题库

| 类别 | 案例数 | Holdout数 |
|---|---:|---:|
| ci-debug | 8 | 2 |
| code-review | 8 | 2 |
| coding | 8 | 2 |

合成题库来源及许可位于各case.json的provenance。题库目录与本次检查结果见evidence/fixture-validation.json。全量命令：

```bash
PYTHONPATH=src DEVOPSPILOT_NO_DOTENV=1 .venv/bin/python scripts/run_offline_checks.py --fail-fast
PYTHONPATH=src DEVOPSPILOT_NO_DOTENV=1 .venv/bin/python benchmarks/devopsbench/runner.py validate-fixtures
```

## 真实任务摘要

交付ID web-d7f99e8a6461；commit 105d74d7fe03f33163dde036ce1d4abba960a3c7；PR8未合并；CI37601566835成功；真实独立审查approved发生在发布后。runtime_clean_completion=false。参见evidence/web-console-delivery.json。

## 尚未完成的评估

没有完整288条同题、同版本、同预算原始结果，不能计算策略间成功率提升、成本改善、时延改善或统计显著性。未取得真实用户反馈或人工节省时间。价格未核验，成本保持unestimated。后续A0–A3含义与实际runner输出一起冻结，不沿用旧大纲相互矛盾的定义。

## 原始记录最小契约

每次记录RC SHA、case ID/version、variant、repetition、model availability、budget、oracle结果、任务成功、运行健康、耗时、tokens、tool/model calls、人工介入与失败分类；失败不能被删除。按类别和holdout分别汇总，所有公开指标必须追溯到原始记录。此报告可据随包证据和源码重建，但未声称缺失的模型对照实验已经执行。
