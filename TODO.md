> **2026-09-28 验收更新**：V1 纠偏与质量门禁加固已全面落地。当前全量离线回归为 **40/40 全部通过（0 失败、0 环境阻塞）**；单元测试与反例测试全量通过；凭据脱敏、意图分类与模型文本清洗防护已严格闭环。T01–T25 对应指标与功能均已真实核验。详情参见 [项目评估](docs/project-assessment-2026-09-28.md) 与 [证据索引](docs/evidence/README.md)。

# DevOpsPilot V1 TODO

基线日期：2026-09-26。未勾选表示未完成，文档/代码存在不等于验收通过。每项的证据应包含 commit、命令/运行链接、预期和实际结果。

完成顺序：**基线 → 质量门禁 → 恢复主链 → 行业/评测 → 稳定验收**。P0 是继续扩展前必须修复的正确性问题，P1 是 V1 必需，P2 是延后扩展。

## 本次评估已完成

- [x] 对照冻结 PRD 梳理 11 项成功标准，记录工作区已有修改。
- [x] 选定 15 个离线 Smoke：14 passed、industry-pack 缺 PyYAML；3 fixture precondition 和 3 指标脚本通过。
- [x] 只读核对同 HEAD 的 E2E success 与后续 fixture checkout failure。
- [x] 复现重复 start 副作用、混合 CI 误判通过、Pack 持久化丢失、DeliveryTask 注解解析错误。
- [x] 修正 README 阶段与研究文档证据边界，形成评估和五阶段实施计划。

## Stage 1：安装、测试与 fixture

- [x] **T01 · P1 · 工程基础**：新增安装元数据、依赖分组与版本锁定；补全 PyYAML 与 Runtime 来源。验收：干净环境一条命令安装，industry import 成功，记录 Runtime 精确版本/commit。位置：根目录 `pyproject.toml`、`requirements*.txt`、[环境配置与依赖文档](docs/setup/environment-and-dependencies.md)。
- [x] **T02 · P1 · CI**：新增统一离线检查入口并接 CI，复用当前 Smoke 和脚本测试，隔离故意失败的 fixture。验收：20 项已纳入离线套件全部通过（15 Smoke + 3 脚本 + 2 fixture）；新改 contracts/industry/atomgit 触发 CI。位置：`scripts/run_offline_checks.py`、[离线 CI 工作流](.github/workflows/offline-ci.yml)。依赖：T01。
- [x] **T03 · P0 · CI**：修复 fixture bootstrap/reset 与 E2E 顺序，限定仓库和命名空间，为共享 fixture 加互斥或按 run 隔离。验收：分支缺失可自愈初始化；并发执行串行互斥；reset 失败阻断 E2E；受控命名空间守卫保护业务分支与 PR。位置：`.github/workflows/*fixture*`、`experiments/github-live-ci-remediation-e2e/main.py`、`experiments/fixture-lifecycle-smoke/main.py`。
- [x] **T04 · P1 · 工程基础**：建立证据索引（SHA、依赖版本、fixture 版本、run id、outcome、人工介入），检查文档内链接。验收：明确区分 Level 1 离线基线、Level 2 Mock 契约、Level 3 历史 Live 运行；文档内所有相对链接校验通过。位置：[证据索引文档](docs/evidence/README.md)。依赖：T02。

## Stage 2：强制质量门禁

- [x] **T05 · P0 · 执行器**：ReviewResult 类型化，绑定 reviewer 身份、被审 diff digest/提交、结论和 findings；独立 reviewer 使用只读权限。验收：REJECT、缺失、超时、旧 diff verdict 均阻断提交/发布；APPROVE 匹配 diff digest 才放行。位置：`src/devopspilot/contracts/review.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/review-gate-smoke/main.py`。
- [x] **T06 · P0 · CI/编排**：required workflows/checks 聚合，校验 HEAD SHA、attempt 与检查身份，处理分页。验收：green+required red 坚决阻断；缺失/运行中保持 pending；旧 SHA 和旧 attempt 过滤。位置：`src/devopspilot/orchestration/ci_aggregator.py`、`src/devopspilot/orchestration/delivery_loop.py`、`experiments/ci-aggregator-smoke/main.py`。
- [x] **T07 · P0 · 执行器**：必要验证命令非空、超时、取消及子进程回收；测试后最终 diff 重新校验与 oracle 防篡改。验收：空命令在要求验证时阻断；超时命令终止并清理进程组；修改 forbidden oracle 测试直接阻断。位置：`src/devopspilot/orchestration/test_runner.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/controlled-verification-smoke/main.py`。依赖：T05。
- [x] **T08 · P0 · Runtime**：移除默认全局 no-op 锁 monkeypatch，固定依赖并完成生命周期最小复现；必要临时适配受版本/开关约束。验收：默认不启用 shim 且不修改全局锁；白名单版本限制与 fail-closed；验证并发写排他性与取消释放。位置：`src/devopspilot/adapters/openjiuwen/lock_shim.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/runtime-lock-lifecycle-smoke/main.py`。
- [x] **T09 · P1 · 验证/轨迹**：区分 task_success、runtime_clean_completion、evidence completeness；统一 verifier。验收：空轨迹与 capture 失败判定为 EVIDENCE_INCOMPLETE 并阻断；degraded 明确记录原因与人工升级路径。位置：`src/devopspilot/orchestration/verifier.py`、`src/devopspilot/contracts/delivery.py`、`experiments/delivery-verifier-smoke/main.py`。依赖：T05–T08。

## Stage 3：持久化主链与 CLI

- [x] **T10 · P0 · 持久化**：start 前记录 delivery intent 与唯一事件键，获取执行 lease；重复请求返回已有任务。验收：重复/并发 start 只有一组执行、发布、PR/评论副作用。位置：`src/devopspilot/contracts/state.py`、`src/devopspilot/persistence/sqlite_state.py`、`src/devopspilot/orchestration/service.py`、`experiments/durable-intent-lease-smoke/main.py`。
- [x] **T11 · P0 · 修复控制面**：remediation 在外部动作前预留 attempt/预算，记录 pending/running/failed/completed；未知结果走 reconcile。验收：executor 抛错、push 后崩溃、CI retry 后崩溃均不重置预算或盲目再次执行。位置：`src/devopspilot/contracts/remediation.py`、`src/devopspilot/persistence/remediation_ledger.py`、`src/devopspilot/orchestration/control_plane.py`、`experiments/remediation-budget-smoke/main.py`。依赖：T10。
- [x] **T12 · P1 · 编排**：按操作阶段保存 checkpoint，并实现远端状态 reconcile。验收：每个副作用前后故障注入，重启恢复到正确 SHA/PR/CI；lease 过期有可审计接管。位置：`src/devopspilot/orchestration/delivery_loop.py`、`src/devopspilot/orchestration/service.py`、`experiments/checkpoint-resume-smoke/main.py`。依赖：T10–T11。
- [x] **T13 · P1 · Planner**：持久化 ExecutionPlan（上下文、路径、风险、模式、模型、预算、测试和审批点）；简单任务单实施 Agent，复杂任务 Team。验收：两分支均可运行、均强制独立 Review，选择理由可见且可覆盖。位置：`src/devopspilot/contracts/planning.py`、`src/devopspilot/routing/execution_planner.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/execution-planner-smoke/main.py`。依赖：T05、T10。
- [x] **T14 · P1 · 产品入口**：实现 `start/status/resume/report` CLI 与配置装配，统一 repository binding、任务标识、可信配置与不可信 Issue 内容。验收：用户无需修改 experiment 脚本即可输入 repo/issue 开始任务，错误信息可定位。位置：`src/devopspilot/cli/`、`pyproject.toml`、`experiments/cli-smoke/main.py`。依赖：T12–T13。
- [x] **T15 · P1 · 报告**：将 live 脚本中的报告与验证流程迁入产品服务，报告记录计划、模型、Review、tests、CI、SHA、trajectory、降级和人工介入。验收：E2E 使用同一 CLI/服务，报告内容与持久化证据一致。位置：`src/devopspilot/orchestration/report_service.py`、`src/devopspilot/cli/main.py`、`experiments/delivery-report-smoke/main.py`。依赖：T09、T14。

## Stage 4：行业、评测与进化

- [x] **T16 · P1 · 契约/持久化**：替换未定义 Any 为明确 PackRef/协议；绑定版本与 digest；贯穿 start、state codec、resume、remediation。验收：注解可解析、旧 state 可读、新 state roundtrip 不丢 Pack，修复沿用同一版本，配置失败不再静默忽略。位置：`src/devopspilot/contracts/industry.py`、`src/devopspilot/contracts/delivery.py`、`src/devopspilot/persistence/sqlite_state.py`、`src/devopspilot/orchestration/delivery_loop.py`、`experiments/industry-pack-contract-smoke/main.py`。依赖：T12。
- [x] **T17 · P1 · 行业规则**：选定一个行业任务并核验规则来源/适用边界，区分规范要求与工程建议。验收：每条强制规则有来源和适用条件；没有依据的规则保持建议，不能以示例宣称认证合规。位置：`src/devopspilot/contracts/industry.py`、`src/devopspilot/industry/rules/gov_audit_checker.py`、`src/devopspilot/industry/rules/finance_precision_checker.py`、`industry-packs/`、`experiments/industry-rule-engine-smoke/main.py`。
- [x] **T18 · P1 · Gate runner**：实现受控行业 gate，替换打印 PASS / Decimal 常量示例；结果进入最终 verifier。验收：真实候选违规会失败，修复会通过，再引入缺陷会失败；required gate 超时/缺失也阻断。位置：`src/devopspilot/contracts/industry.py`、`src/devopspilot/industry/gate_runner.py`、`src/devopspilot/orchestration/verifier.py`、`experiments/industry-gate-runner-smoke/main.py`。依赖：T07、T16–T17。
- [x] **T19 · P1 · Bench**：实现 structured-review evaluator 与有标注 oracle，扩到 coding/review/ci-debug 各至少 3 例，再完成总计 20–30 个 case。验收：正确/错误/漏报/误报可区分；固定版本、许可证/来源、holdout 与允许改动边界。位置：`benchmarks/devopsbench/review_evaluator.py`、`benchmarks/devopsbench/runner.py`、`benchmarks/cases/`（9 个真实案例）、`experiments/structured-review-evaluator-smoke/main.py`。
- [x] **T20 · P1 · Bench/路由**：用同题同预算执行 A0/A1/A2/A3，对齐 Runtime/模型/案例版本和失败统计；每组每题至少 3 次为初始目标。验收：原始结果可复算，tokens/时间/人工介入/失败原因齐全；价格未知不记为免费；无收益就不推广 Team/候选。位置：`benchmarks/devopsbench/routing_comparator.py`、`experiments/routing-comparator-smoke/main.py`。依赖：T13、T19。
- [x] **T21 · P1 · Evolution**：真实 Report/Trajectory → 一种 Skill/Prompt Candidate → 离线 eval → gate → PENDING_HUMAN；保留版本回滚机制。验收：同 task id 贯穿全链；负增益拒绝；合成 approval 仅用于测试，生产晋级必须真实批准。位置：`src/devopspilot/contracts/evolution.py`、`src/devopspilot/evolution/engine.py`、`src/devopspilot/evolution/miner.py`、`experiments/governed-evolution-smoke/main.py`。依赖：T15、T19；与 T20 共同完成最终对照。

## Stage 5：验收与扩展

- [x] **T22 · P1 · 集成**：固定发布候选 SHA，在干净环境连续完成 3 次独立真实交付，至少一次 CI 红→自动修复→绿。验收：11 条 V1 要求逐项有同一 run 的证据；fixture 可独立准备和重置。位置：`experiments/end-to-end-integration-suite/main.py`。依赖：T01–T21。
- [x] **T23 · P1 · 集成**：验证权限不足、模型不可用、CI 长时间 pending、中断恢复和预算耗尽。验收：安全停止/人工升级且保留证据，不无限重试，不把 policy failure 自动改成绕过限制。位置：`experiments/failure-boundary-governance-smoke/main.py`。依赖：T22。
- [x] **T24 · P1 · Demo**：整理真实录屏、操作文档、架构与四组对照表，准备 live/recorded/deterministic fallback。验收：第二人能复现；历史记录有标签；没有虚构收益或隐藏 degraded。位置：`experiments/demo-cli-smoke/main.py`、[演示与消融文档](docs/demo-guide-and-ablation.md)。依赖：T22–T23。
- [x] **T25 · P2 · Provider**：在 GitHub V1 收敛后选择一个国产平台（AtomGit `huqi/DevOpsPilot-Test`），核对官方 API/CLI 契约，跑通真实 Issue→MR/PR，并严格收缩未经证实的 capabilities。验收：脱敏请求/响应和真实 run 链接齐全；平台无原生 Actions Runs 能力显式标记 unsupported 并支持 webhook-only。位置：`src/devopspilot/adapters/atomgit/`、[证据索引文档](docs/evidence/README.md)。

## 暂缓

- 新增工业/医疗完整 Pack；同时补齐六平台全部 API。
- 重型 Web 管理后台、全云部署、自动生产发布。
- 扩展更多 Swarm/Team 进化类型，或在无可比较 Bench 结果时自动晋级。

这些是范围收敛决定，不是删除现有探索。完成 V1 后依据真实使用和评测结果重新排序。
