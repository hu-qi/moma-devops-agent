# DevOpsPilot 证据索引与可信度分级体系

基线日期：2026-09-26  
对应任务：`TODO.md` T04 · P1 · 工程基础

## 1. 证据三层分类原则

为了避免把新增未提交实现误标为既有已验证、把离线 Mock 误标为云端原生支持、或把偶然的单次 Live 成功误标为稳定交付，DevOpsPilot 将所有证据严格分为三层：

| 分类 | 证据属性 | 适用范围与边界声明 | 代表性条目 |
|---|---|---|---|
| **Level 1: 本地离线回归 (Current Offline Baseline)** | 完全可确定性复现、零外部凭据消耗 | 仅证明核心契约、状态存储、行业规则加载及离线算法逻辑正确；不依赖任何远端服务。 | `scripts/run_offline_checks.py` (40/40 PASS) |
| **Level 2: 单元与平台契约 Mock (Contract & Mock)** | 基于 FakeClient / Mock 测试 | 证明代码符合内部 Provider 契约；**不证明**真实平台 API 行为（例如 AtomGit / CNB 目前基于 Fake 契约，未经生产 Live 验证）。 | `*-reference-adapter-smoke`、`provider-contract-smoke` |
| **Level 3: 历史远端真实运行 (Historical Live Evidence)** | 真实远端调用记录（GitHub Actions / MoMA） | 证明特定时间特定环境真实执行成功；必须同时记录降级情况（degraded）、耗时、人工介入与复现稳定性，不等于 100% 生产稳定性。 | GitHub E2E Run `36086881849`、MoMA Spike `35877219890` |

---

## 2. 远端真实运行索引 (Historical Live Runs)

| Run ID | 关联功能 / 场景 | Git SHA | 外部平台 | 结果 (Outcome) | 人工介入 / 降级标记 | 证据与归因说明 |
|---|---|---|---|---|---|---|
| [36086881849](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086881849) | GitHub Live CI 修复 E2E | `13034d6` | GitHub + MoMA | SUCCESS | **DEGRADED**: `agentteam_timeout 240s`，无人工直接修改代码 | 首次验证 CI 失败自动读取日志并同分支推修复 commit。 |
| [36086892725](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086892725) | GitHub Live CI 修复 E2E | `13034d6` | GitHub | FAILURE | 无人工介入 | Checkout 阶段因 fixture 分支不存在而失败；确认为调度顺序而非推理失败。 |
| [36087239486](https://github.com/hu-qi/moma-devops-agent/actions/runs/36087239486) | CI Remediation Fixture CI | `13034d6` | GitHub | SUCCESS | 无 | 证明处于 broken 状态的目标测试用例会如期红灯。 |
| [36087239543](https://github.com/hu-qi/moma-devops-agent/actions/runs/36087239486) | CI Remediation Fixture Reset | `13034d6` | GitHub | FAILURE | 需排查重置脚本并发环境 | 重置工作流在单分支上竞争导致失败。已在 T03 增加互斥与自愈机制。 |
| [35876800666](https://github.com/hu-qi/moma-devops-agent/actions/runs/35876800666) | MoMA Live Smoke | 历史 Commit | MoMA API | SUCCESS | 无 | 验证基础 OpenAI 兼容接口调用能力。 |
| [35877219890](https://github.com/hu-qi/moma-devops-agent/actions/runs/35877219890) | MoMA Capability Spikes | 历史 Commit | MoMA API | SUCCESS | 无 | 验证 MoMA 角色模型分发与推理链路。 |
| [AtomGit-Issue-1](https://gitcode.com/huqi/DevOpsPilot-Test/issues/1) | T25 AtomGit 真实仓库 Issue 交付 | `2160c8b` | AtomGit | SUCCESS | 无人工直接修改代码 | 真实创建并关联任务 Issue #1 与提交。 |
| [AtomGit-MR-1](https://gitcode.com/huqi/DevOpsPilot-Test/merge_requests/1) | T25 AtomGit 真实 MR 交付与能力边界核验 | `2160c8b` | AtomGit | SUCCESS | **能力边界收缩**：原生 Actions Runs API unsupported，依赖外部 Runner/Webhook | 验证真实分支 `feat/health-check` 推送、OpenAPI 创建 MR #1，并严格收缩国产平台 CI 能力声明。 |
| [AtomGit-Issue-2](https://atomgit.com/huqi/DevOpsPilot-Test/issues/2) | 只读 Issue 意图分流与直接评论交付 (`deliv-b424ceed`) | `60c8622` | AtomGit + MoMA | SUCCESS | **只读问答闭环**：分类为 `inquiry`，直接回复结构化文件清单 | 验证不建分支、不开 PR、不写脏代码；`strip_think_tags` 完全剔除思考内容，结构化 Markdown 回复。 |

---

## 3. 当前离线基线与验证结果 (Current Verification)

- **基线日期**: 2026-09-28 (全量回归加固完成)
- **执行命令**: `python3 scripts/run_offline_checks.py`
- **通过率**: 40 项离线检查全部通过 (100% PASS, 0 failed, 0 degraded)
- **包含套件**:
  1. `provider-contract-smoke` (PASS)
  2. `model-routing-smoke` (PASS)
  3. `trajectory-smoke` (PASS)
  4. `delivery-loop-smoke` (PASS)
  5. `delivery-state-store-smoke` (PASS)
  6. `durable-delivery-smoke` (PASS)
  7. `git-publisher-smoke` (PASS)
  8. `delivery-pipeline-smoke` (PASS)
  9. `autonomous-control-plane-smoke` (PASS)
  10. `remediation-adapter-smoke` (PASS)
  11. `evolution-gate-smoke` (PASS)
  12. `github-reference-adapter-smoke` (PASS)
  13. `cnb-reference-adapter-smoke` (PASS)
  14. `atomgit-reference-adapter-smoke` (PASS)
  15. `industry-pack-smoke` (PASS)
  16. `review-gate-smoke` (PASS, Stage 2 新增)
  17. `ci-aggregator-smoke` (PASS, Stage 2 新增)
  18. `controlled-verification-smoke` (PASS, Stage 2 新增)
  19. `runtime-lock-lifecycle-smoke` (PASS, Stage 2 新增)
  20. `delivery-verifier-smoke` (PASS, Stage 2 新增)
  21. `durable-intent-lease-smoke` (PASS, Stage 3 新增)
  22. `remediation-budget-smoke` (PASS, Stage 3 新增)
  23. `checkpoint-resume-smoke` (PASS, Stage 3 新增)
  24. `execution-planner-smoke` (PASS, Stage 3 新增)
  25. `cli-smoke` (PASS, Stage 3 新增)
  26. `delivery-report-smoke` (PASS, Stage 3 新增)
  27. `industry-pack-contract-smoke` (PASS, Stage 4 新增)
  28. `industry-rule-engine-smoke` (PASS, Stage 4 新增)
  29. `industry-gate-runner-smoke` (PASS, Stage 4 新增)
  30. `structured-review-evaluator-smoke` (PASS, Stage 4 新增)
  31. `routing-comparator-smoke` (PASS, Stage 4 新增)
  32. `governed-evolution-smoke` (PASS, Stage 4 新增)
  33. `end-to-end-integration-suite` (PASS, Stage 5 新增)
  34. `failure-boundary-governance-smoke` (PASS, Stage 5 新增)
  35. `demo-cli-smoke` (PASS, Stage 5 新增)
  36. `model-routing-profiler` (PASS)
  37. `trajectory-metrics` (PASS)
  38. `devopsbench-runtime-metrics` (PASS)
  39. `fixture-lifecycle-smoke` (PASS)
  40. `devopsbench-validate-fixtures` (PASS)

---

## 4. 依赖与环境元数据

- **Python 版本**: 3.11.14
- **离线核心依赖**: `PyYAML==6.0.2`
- **测试框架**: `pytest==8.3.5`
- **Runtime 基线**:
  - Source Repository: `https://github.com/openJiuwen-ai/agent-core.git`
  - Target Branch: `release/v0.1.19`
  - Resolved Commit SHA: `6f3a33fbb93aece65105c477c573057fead0e8dd`
  - Package Metadata: `0.1.18` (由于上游分支发布周期原因，安装后元数据报告 0.1.18，需如实记录)
