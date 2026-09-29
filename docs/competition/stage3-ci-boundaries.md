# CI 平台边界：GitHub 主线与 AtomGit 扩展（C18）

对应任务：`docs/competition/TODO.md` C18。基线：2026-09-29。本文只声明已核验的能力，未经核验的一律标注"未核验"。

## 1. GitHub —— 完整 CI 主线

| 能力 | 状态 | 证据 |
|---|---|---|
| Actions Runs 查询/日志/按 SHA 过滤 | 已核验 | `src/devopspilot/adapters/github/ci.py`；历史 Live Run `36086881849`（红→自动修复→绿） |
| failed-run retry | 已核验（代码路径） | `GitHubCIProvider` + `ci-aggregator-smoke` |
| required checks 聚合（HEAD SHA/attempt 过滤、分页） | 已核验 | `src/devopspilot/orchestration/ci_aggregator.py`（T06） |
| webhook 签名（X-Hub-Signature-256） | 已核验 | `src/devopspilot/adapters/github/scm.py` |

**结论**：Stage 3 三轮 Live 的 CI 主线使用 GitHub；历史 run 不得冒充当前 RC 证据。

## 2. AtomGit —— 扩展交付，webhook-only CI 边界

| 能力 | 状态 | 证据 |
|---|---|---|
| Issue 读取 / 评论 / MR 创建 / 分支推送 | 已核验（真实仓库） | `AtomGit-Issue-1`、`AtomGit-MR-1`、`AtomGit-Issue-2`（`docs/evidence/README.md`） |
| **原生 Actions Runs API** | **unsupported** | 真实核验记录见 `AtomGit-MR-1`：能力边界收缩，依赖外部 Runner |
| webhook 接收（HMAC 签名） | 已核验（代码契约） | `src/devopspilot/adapters/atomgit/scm.py` `_verify_webhook` / `normalize_webhook` |
| failed-run retry / required-checks 原生聚合 | **不支持**（无原生 Runs API 即无重试与聚合对象） | 由上推导 |

**结论**：
1. AtomGit 的 CI 结果只能通过 **webhook 推送** 进入 DevOpsPilot，或由外部 Runner 把状态写回；`reconcile_ci` 的轮询聚合在该平台不可用，轮到 webhook-only 路径。
2. CI 失败自动修复（C13/S2 场景）在 AtomGit 上**不可用**，不得宣称；修复能力仅对支持 Runs 查询的平台（GitHub）声明。
3. 未核验事项：AtomGit webhook 的事件负载字段、速率限制、重试语义——接入前需单独核验，不得编造。

## 3. 对 Stage 3 的约束

- C17 的 S2（CI 红修复）与 S4（CI reconcile）只对 GitHub 主线签收。
- AtomGit 仅签收：Issue→只读问答或代码变更→MR 创建（`AtomGit-Issue-2`、`AtomGit-MR-1` 模式），CI 环节标记 `unsupported (webhook-only)`。
- 任何材料不得把 AtomGit 描述为"原生 Actions 支持"。
