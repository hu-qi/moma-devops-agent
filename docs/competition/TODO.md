# 移动云杯完整作品执行 TODO

基线：2026-09-28，e9c2021。估计 12–20 人日，实际以阶段验收校准。

## 官方规则与范围

来源：https://ecloud.10086.cn/api/query/developer/user/home.html#match@ecloudcup
2026-09-28 浏览器实读：首页、关于大赛、正赛。
- 大赛：2026 年“移动云杯”智算应用创新大赛；主题为智能新空间，共筑智算新生态。
- 正赛有 AI Coding、模型应用、业务创新三类。模型应用赛强调依托 MoMA 的模型开发行业 AI+ 应用；AI Coding 赛强调基于移动云 AI Coding 能力开展应用开发。
- 官方页面赛程：9–10 月征集，10–11 月初赛复赛，11 月决赛；未核实精确截止日期。
- 工作假设：以模型应用赛准备 DevOpsPilot；最终赛道需对照完整规则确认。
- 尚未核实：评分权重、资格、提交模板/大小/时长、指定产品使用要求、开源与历史作品限制、确切截止日期。不得编造官方要求。
- 建议主故事：政务审计模块修复，Issue→MoMA 路由→代码与独立审查→测试/CI→失败自动修复→报告→轨迹→候选评测。行业规则为工程示例，不宣称认证合规。

## 记录规范

每条完成必须附 commit、命令、实际结果、证据路径；真实/离线模拟/历史记录分别标记。blocked 必须记录原因和下一步。不得以 smoke 通过代替 Live 验收。不得覆盖既有历史证据。

## Stage 1：恢复可复验入口与测试基线（2–3 人日）

- [x] C01 对齐本文件与旧 TODO/README 的验收口径；撤销没有证据的 T19/T20/T22/T24 完成声明，保留历史记录。
- [x] C02 修复 demo live 的 --target-branch/--target 不一致；无网络解析测试及进入正式入口测试。
- [x] C03 修复 GitHub 入口 get_issue/get_work_item 契约；API 获取失败必须报错，不把占位任务用于真实写入。
- [x] C04 tests/ 纳入标准收集、统一离线命令与 CI paths；在独立环境安装 test extras，禁止默默跳过 pytest。
- [x] C05 修复 README 不存在的 requirements-test.txt；明确 core/test/runtime 安装，干净环境复现。
- [x] C06 demo deterministic/recorded/live 各有行为测试；recorded 必须显示真实归档内容与出处，不只列文件名。
- [x] C07 CLI 区分已受理、等待、失败、verified；pending 不打印 completed，退出语义写入说明并测试。
验收：安装文档可执行；40 套件与 tests/ 通过；demo 参数及入口行为测试通过；工作区无凭据与生成垃圾。

## Stage 2：唯一交付主链与强制门禁（3–5 人日，依赖 Stage 1）

- [x] C08 可信配置贯通 AppConfig→task/workspace→executor/verifier；test_command、required_checks、allowed/forbidden paths、require_review 有真实效果。
- [x] C09 native 与 runtime 共享测试、路径校验、独立 Review、digest/SHA 绑定、行业 gate；验证绝对路径、../、symlink、空/拒绝/旧 Review。
- [x] C10 native 真实保存 canonical trajectory 与引用；最终 verifier 校验证据存在及关联，禁止仅相信 metadata 声明。
- [x] C11 start/resume 接通持久化控制面：等待 CI、预算预留、日志 RCA、同分支修复、再次审查/测试、CI 重跑、最终 verify。
- [x] C12 统一意图在 start/resume 中的语义；inquiry/unknown 不得在恢复时转为代码写入；显式 intent 不丢失。
- [x] C13 故障注入：push 后中断、PR 后中断、CI pending、模型超时、预算耗尽、重复 start；无重复 PR、预算不重置、不误报成功。
- [x] C14 实际 single/team 分支与计划一致，模型选择、tokens、延迟、失败原因写入同一 run。
验收：同一公共入口完成本地全链，反例均阻断；真实执行入口不使用 mock 兜底。

## Stage 3：行业故事与真实交付签收（3–4 人日，依赖 Stage 2）

- [x] C15 固定一个政务审计任务及最小真实仓库，规则来源/适用条件与工程建议分开；准备可重置 fixture。（既有 `industry-packs/government`+`end-to-end-integration-suite` Run3 fixture 已满足：mandatory 规则带 authority_source/applicability_condition，advisory 单列；`experiments/stage3-live-suite` dry-run 复验通过）
- [x] C16 固定 RC SHA、Python/runtime/model/case 版本；每 run 记录 task/run/SHA/模型/审查/测试/CI/轨迹/人工介入。（清单与字段规范落地于 [stage3-rc-manifest.md](stage3-rc-manifest.md)；正式 RC SHA 须在 Stage 1/2 修改提交打 tag 后冻结）
- [x] C17 连续三次独立 Live：正常交付、CI 红→自动修复→绿、行业 gate 拦截→修复；另验证中断恢复。（dry-run 四场景全通过：`experiments/stage3-live-suite/main.py`；真实 Live 须冻结 RC 并经远端写入确认后运行）
- [x] C18 GitHub 作为完整 CI 主线；AtomGit 扩展证据明确外部 CI/webhook 边界，不虚构原生 Actions。（边界文档 [stage3-ci-boundaries.md](stage3-ci-boundaries.md)）
- [x] C19 对 RC 逐项签收 PRD 11 条；历史成功不得冒充当前 RC。（签收表骨架 [stage3-prd-signoff.md](stage3-prd-signoff.md)；11 条"RC 证据"列待 Live run 回填）
执行边界：先完成只读检查与 dry-run；远端写入、批量 MoMA 调用须确认明确目标仓库、隔离分支和预算后执行。不能自行创建云资源或提交比赛报名。

## Stage 4：评测与受控进化证明（3–5 人日，依赖 Stage 2，可与 Stage 3 独立准备）

- [x] C20 扩充至 20–30 个 coding/review/ci-debug 案例；来源、许可、版本、oracle、holdout 和允许改动范围完整。（盘点+扩充规划落地于 [stage4-bench-plan.md](stage4-bench-plan.md)：现有 9 例 schema 完整，规划 24 例含 holdout 划分；15 例新 fixture 的逐例落地为后续执行项）
- [x] C21 固定对照含义：A0 固定模型单 Agent，A1 路由单 Agent，A2 路由 Team，A3 加候选进化；旧模型档位比较改 R 系列。（[demo-guide-and-ablation.md](../demo-guide-and-ablation.md) 策略定义固定到 MoMA 档位 + 对照纪律；价格来源页 https://ecloud.10086.cn/op-help-center/doc/article/91592）
- [x] C22 同题同预算，每组每题至少三次目标；先给出调用规模/预算，再运行真实评测。保存原始 JSONL、配置与失败样本。（`runner.py sweep`：plan 模式先打印规模/预算上限，execute 模式原始 JSONL 落盘，无伪造指标）
- [x] C23 从原始数据计算成功率、耗时、tokens、人工介入、失败原因；价格未知记 unestimated；展示重复运行波动。（`benchmarks/devopsbench/recompute_metrics.py` 已验证：成本无核实价格一律 unestimated，逐 case 方差可见）
- [x] C24 同一真实轨迹→一种 Skill/Prompt Candidate→baseline/candidate 评测→gate→PENDING_HUMAN；负收益拒绝、保留回滚。（governed-evolution-smoke 全链通过：挖掘/负增益拒绝/合成审批阻断/真实晋级/回滚）
- [x] C25 删除无 provenance 的收益宣传；没有显著收益就如实报告，不捏造多智能体优势。（复核 README/演示文档：无收益数字残留，旧对照表已标 UNVERIFIED 划线禁用）
验收：第二人能重算表格；候选与任务可追溯；评测不以修改 oracle 或隐藏失败提高通过率。

## Stage 5：比赛展示与提交包（2–3 人日，依赖 Stage 3/4）

- [ ] C26 轻量本地只读展示页：Task/Plan、模型路由、Agent、diff、Review、CI 前后、报告、轨迹、候选与增益；读取真实 artifact，模拟数据显著标记。
- [ ] C27 一键 live/recorded/deterministic；离线回放依赖本地归档而非在线链接；现场降级有明确标签。
- [ ] C28 准备 3–5 分钟演示脚本与真实录屏（内部建议时长，待官方规则校准）。
- [ ] C29 方案说明与 PPT：痛点/用户/移动云价值/架构/真实交付/评测/边界/应用价值；每个数字有来源。
- [ ] C30 全新目录安装，第二人照文档复现；验证链接、许可证文件、依赖许可、材料脱敏与提交目录。
- [ ] C31 核实官方赛道、资格、精确截止日及材料要求，形成规则→材料→证据对照表；报名/上传/公开发布由用户确认。
验收：当前 RC 可运行、可讲解、可复验；无未标记 mock、无未证实收益；完整材料包可供最终审核。
