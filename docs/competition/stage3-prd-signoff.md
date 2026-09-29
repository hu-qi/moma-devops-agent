# RC 逐项签收表 —— PRD 11 条成功标准（C19）

对应任务：`docs/competition/TODO.md` C19。PRD 原文：`PRD/02-v1-scope.md` §5。
基线 RC：**待冻结**（Stage 1/2 修改提交并打 tag 后回填 `docs/competition/stage3-rc-manifest.md`）。

> 规则：只有**当前 RC 同一 run** 的证据（见 stage3-rc-manifest.md §2 的 run 记录）才允许填入"RC 证据"列；历史成功（如 GitHub run `36086881849`）只能放"历史参考"列，**不得冒充当前 RC**。签收在三轮 Live 完成后执行；本表为准备好的骨架。

| # | PRD 要求 | 签收场景 | RC 证据（同一 run） | 状态 | 历史参考 |
|---|---|---|---|---|---|
| 1 | 正确理解任务与仓库上下文 | S1 | 待 Live | ☐ | AtomGit-Issue-2（意图分流） |
| 2 | 形成可解释执行计划 | S1 | 待 Live（`execution_rationale` 字段） | ☐ | — |
| 3 | 根据任务选择模型能力档 | S1 | 待 Live（`models` 字段） | ☐ | MoMA Spike `35877219890` |
| 4 | 必要时动态组建 AgentTeam | S1/S3（complex 分支） | 待 Live（`plan_json.mode`） | ☐ | — |
| 5 | 完成代码修改与测试 | S1 | 待 Live（`tests` 字段） | ☐ | — |
| 6 | 由独立 Reviewer 验证结果 | 全部 | 待 Live（`review_verdict` + digest 绑定） | ☐ | — |
| 7 | 创建 PR/MR | S1 | 待 Live（`ci.run_id` 关联 PR） | ☐ | AtomGit-MR-1 |
| 8 | CI 结果 + 失败自动 RCA/修复 ≥1 次 | S2 | 待 Live（`remediation` 数组；**仅 GitHub 主线**，AtomGit webhook-only 不适用） | ☐ | Run `36086881849` |
| 9 | 输出 Delivery Report | 全部 | 待 Live（`devopspilot report` 输出与 state 一致） | ☐ | — |
| 10 | 保存完整 Trajectory | 全部 | 待 Live（`trajectory.disk_file`，verifier 磁盘核验） | ☐ | — |
| 11 | ≥1 个可离线评测 Evolution Candidate | S1 后 | 待 Live（同 task id 贯穿 candidate 链） | ☐ | governed-evolution-smoke |

## 签收流程

1. 冻结 RC tag → 回填 manifest。
2. 确认远端写入目标（仓库、隔离分支、预算）后运行 `experiments/stage3-live-suite/main.py --live`。
3. 每个 run 产出 manifest §2 结构的 JSON 归档至 `docs/evidence/`。
4. 用同一 run 的 JSON 逐条回填上表"RC 证据"，11 条全部有同一 run 证据方算 S3 验收通过。
5. 中断恢复（S4）单独立项记录，不抵充 11 条。
