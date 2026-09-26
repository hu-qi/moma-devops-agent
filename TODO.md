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

- [ ] **T01 · P1 · 工程基础**：新增安装元数据、依赖分组与版本锁定；补全 PyYAML 与 Runtime 来源。验收：干净环境一条命令安装，industry import 成功，记录 Runtime 精确版本/commit。位置：根目录配置、setup 文档。
- [ ] **T02 · P1 · CI**：新增统一离线检查入口并接 CI，复用当前 Smoke 和脚本测试，隔离故意失败的 fixture。验收：所有已纳入离线套件通过；新改 contracts/industry/atomgit 会触发相关检查。依赖：T01。
- [ ] **T03 · P0 · CI**：修复 fixture bootstrap/reset 与 E2E 顺序，限定仓库和命名空间，为共享 fixture 加互斥或按 run 隔离。验收：分支缺失可初始化；重复启动不互删；reset 失败阻断 E2E；业务 PR 不会被 fixture cleanup 关闭。位置：`.github/workflows/*fixture*`、live E2E。
- [ ] **T04 · P1 · 工程基础**：建立证据索引（SHA、依赖版本、fixture 版本、run id、outcome、人工介入），检查文档内链接。验收：mock、一次 live 成功、当前验收三者可区分；不把新增未提交实现标成既有 CI 已验证。依赖：T02。

## Stage 2：强制质量门禁

- [ ] **T05 · P0 · 执行器**：ReviewResult 类型化，绑定 reviewer 身份、被审 diff digest/提交、结论和 findings；独立 reviewer 使用只读权限。验收：REJECT、缺失、超时、旧 diff verdict 均阻断提交/发布；APPROVE 加有效测试才放行。位置：contracts、openjiuwen/executor。
- [ ] **T06 · P0 · CI/编排**：required workflows/checks 聚合，校验 HEAD SHA、attempt 与检查身份，处理分页。验收：green+required red 阻断；缺失保持 pending；无关 workflow 不误判；旧 SHA 和旧 attempt 不放行。位置：delivery_loop、CI contracts/adapters。
- [ ] **T07 · P0 · 执行器**：必要验证命令非空、超时、取消及子进程回收；测试后最终 diff 必须重新校验。验收：空命令不可声称通过；挂起命令可停止；测试改源码后不能复用旧 Review；Agent 不能修改 oracle 逃避验证。依赖：T05。
- [ ] **T08 · P0 · Runtime**：移除默认全局 no-op 锁 monkeypatch，固定依赖并完成生命周期最小复现；必要临时适配受版本/开关约束。验收：并发写/取消/shutdown 有明确结果；未支持版本显式报错；导入业务包不修改第三方全局同步行为。位置：openjiuwen/executor。
- [ ] **T09 · P1 · 验证/轨迹**：区分 task_success、runtime_clean_completion、evidence completeness；统一 verifier。验收：空轨迹、capture 失败不能被报告成完整交付成功；degraded 有原因、预算和人工升级路径。依赖：T05–T08。

## Stage 3：持久化主链与 CLI

- [ ] **T10 · P0 · 持久化**：start 前记录 delivery intent 与唯一事件键，获取执行 lease；重复请求返回已有任务。验收：重复/并发 start 只有一组执行、发布、PR/评论副作用。位置：service、sqlite_state、contracts/state。
- [ ] **T11 · P0 · 修复控制面**：remediation 在外部动作前预留 attempt/预算，记录 pending/running/failed/completed；未知结果走 reconcile。验收：executor 抛错、push 后崩溃、CI retry 后崩溃均不重置预算或盲目再次执行。依赖：T10。
- [ ] **T12 · P1 · 编排**：按操作阶段保存 checkpoint，并实现远端状态 reconcile。验收：每个副作用前后故障注入，重启恢复到正确 SHA/PR/CI；lease 过期有可审计接管。依赖：T10–T11。
- [ ] **T13 · P1 · Planner**：持久化 ExecutionPlan（上下文、路径、风险、模式、模型、预算、测试和审批点）；简单任务单实施 Agent，复杂任务 Team。验收：两分支均可运行、均强制独立 Review，选择理由可见且可覆盖。依赖：T05、T10。
- [ ] **T14 · P1 · 产品入口**：实现 `start/status/resume/report` CLI 与配置装配，统一 repository binding、任务标识、可信配置与不可信 Issue 内容。验收：用户无需修改 experiment 脚本即可输入 repo/issue 开始任务，错误信息可定位。依赖：T12–T13。
- [ ] **T15 · P1 · 报告**：将 live 脚本中的报告与验证流程迁入产品服务，报告记录计划、模型、Review、tests、CI、SHA、trajectory、降级和人工介入。验收：E2E 使用同一 CLI/服务，报告内容与持久化证据一致。依赖：T09、T14。

## Stage 4：行业、评测与进化

- [ ] **T16 · P1 · 契约/持久化**：替换未定义 Any 为明确 PackRef/协议；绑定版本与 digest；贯穿 start、state codec、resume、remediation。验收：注解可解析、旧 state 可读、新 state roundtrip 不丢 Pack，修复沿用同一版本，配置失败不再静默忽略。依赖：T12。
- [ ] **T17 · P1 · 行业规则**：选定一个行业任务并核验规则来源/适用边界，区分规范要求与工程建议。验收：每条强制规则有来源和适用条件；没有依据的规则保持建议，不能以示例宣称认证合规。
- [ ] **T18 · P1 · Gate runner**：实现受控行业 gate，替换打印 PASS / Decimal 常量示例；结果进入最终 verifier。验收：真实候选违规会失败，修复会通过，再引入缺陷会失败；required gate 超时/缺失也阻断。依赖：T07、T16–T17。
- [ ] **T19 · P1 · Bench**：实现 structured-review evaluator 与有标注 oracle，扩到 coding/review/ci-debug 各至少 3 例，再完成总计 20–30 个 case。验收：正确/错误/漏报/误报可区分；固定版本、许可证/来源、holdout 与允许改动边界。
- [ ] **T20 · P1 · Bench/路由**：用同题同预算执行 A0/A1/A2/A3，对齐 Runtime/模型/案例版本和失败统计；每组每题至少 3 次为初始目标。验收：原始结果可复算，tokens/时间/人工介入/失败原因齐全；价格未知不记为免费；无收益就不推广 Team/候选。依赖：T13、T19。
- [ ] **T21 · P1 · Evolution**：真实 Report/Trajectory → 一种 Skill/Prompt Candidate → 离线 eval → gate → PENDING_HUMAN；保留版本回滚机制。验收：同 task id 贯穿全链；负增益拒绝；合成 approval 仅用于测试，生产晋级必须真实批准。依赖：T15、T19；与 T20 共同完成最终对照。

## Stage 5：验收与扩展

- [ ] **T22 · P1 · 集成**：固定发布候选 SHA，在干净环境连续完成 3 次独立真实交付，至少一次 CI 红→自动修复→绿。验收：11 条 V1 要求逐项有同一 run 的证据；fixture 可独立准备和重置。依赖：T01–T21。
- [ ] **T23 · P1 · 集成**：验证权限不足、模型不可用、CI 长时间 pending、中断恢复和预算耗尽。验收：安全停止/人工升级且保留证据，不无限重试，不把 policy failure 自动改成绕过限制。依赖：T22。
- [ ] **T24 · P1 · Demo**：整理真实录屏、操作文档、架构与四组对照表，准备 live/recorded/deterministic fallback。验收：第二人能复现；历史记录有标签；没有虚构收益或隐藏 degraded。依赖：T22–T23。
- [ ] **T25 · P2 · Provider**：在 GitHub V1 收敛后选择一个国产平台，先核对官方 API/CLI 契约，再跑真实 Issue→MR/PR→CI，收缩未经证实的 capabilities。验收：脱敏请求/响应和真实 run 链接齐全；平台无某能力则显式 unsupported。主线 V1 不依赖此项，未完成不得宣称该平台已 live 支持。

## 暂缓

- 新增工业/医疗完整 Pack；同时补齐六平台全部 API。
- 重型 Web 管理后台、全云部署、自动生产发布。
- 扩展更多 Swarm/Team 进化类型，或在无可比较 Bench 结果时自动晋级。

这些是范围收敛决定，不是删除现有探索。完成 V1 后依据真实使用和评测结果重新排序。
