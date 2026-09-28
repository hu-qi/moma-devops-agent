# 2026-09-28 项目完成度与纠偏评估

## 结论与口径

当前定位：**核心组件已形成，产品集成仍有断点，尚不具备 V1 验收通过条件**。建议暂停新增平台、品牌包装和进化类型，先恢复质量门禁与唯一交付主链。

以冻结 PRD 的可复现交付为目标，工程判断：组件实现约 **70–80%**、V1 集成约 **45–60%**、发布验收准备约 **25–40%**。这是按代码覆盖、主链接通和证据完整性给出的区间估计，不是任务勾选率或测试通过率，不能合成为“已完成 100%”。没有当前候选版本的完整 Live 签收，因此 11 项标准不能据此宣布全部完成。

评估对象为 HEAD `10bf921d6409cacdfc6a0343b402606e21f3bd9e` 加当前工作区：评估开始时已有 12 个已跟踪文件修改（631 行新增、62 行删除）以及新建的 MoMA client、branding、intent、inquiry、utils 与四个测试文件。结论涵盖这些未提交实现；不能归因成 HEAD 单独的发布质量。本次未修改业务代码、未提交已有工作、未触发真实模型调用或远端写入。

## 实测基线

| 检查 | 当前结果 | 解释 |
|---|---|---|
| `.venv/bin/python scripts/run_offline_checks.py` | 32 passed / 8 failed | 含 Git 签名配置影响，不能都算业务缺陷 |
| 仅为临时夹具关闭提交签名后重跑 | 36 passed / 4 failed | 不改全局配置、不绕过 hooks；见下方明细 |
| 四个新增 pytest 文件 | 未执行 | 当前 `.venv` 缺少 pytest；统一 runner 也未注册这四个文件 |
| verifier 三个负向探针 | 三个均错误放行 | 缺 review、错误 CI SHA、published=False 均返回 accepted=True / verified_clean |
| benchmark case 清点 | 9 个，三类各 3 个 | 尚未达到 TODO T19 的 20–30 个目标 |
| 当前候选 Live E2E | 未验证 | 历史链接没有在本次重新查询；不能沿用为当前工作区验收 |

隔离签名命令：`GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=commit.gpgsign GIT_CONFIG_VALUE_0=false .venv/bin/python scripts/run_offline_checks.py`。

剩余失败：
- `delivery-loop-smoke`、`delivery-pipeline-smoke`：断言正文包含 `DevOpsPilot Delivery` 失败。需要判定新的品牌展示契约并同步行为测试，不能简单删断言。
- `cli-smoke`：`GitHubSCMProvider.__init__() got an unexpected keyword argument 'token'`。真实装配需传入 GitHubAPIClient；CIProvider 同样按 client 注入。
- `remediation-adapter-smoke`：本地 HTTPServer bind 被沙箱拒绝（PermissionError）。属于环境受限、尚未验证，不算产品失败或通过。

原始日志：[默认环境](evidence/assessment-2026-09-28-offline.log)、[隔离签名](evidence/assessment-2026-09-28-isolated.log)。本次没有干净环境重新安装，安装可复现性仍待验证。

## PRD 11 项签收状态

| 标准 | 实现与现有证据 | 当前验收判断 |
|---|---|---|
| 1 任务与上下文理解 | SCM/TaskProfile/intent 已有；native 路径仅文件清单与 README 片段 | 部分；复杂代码上下文不足，问答需单独验收 |
| 2 可解释计划 | ExecutionPlan、Planner、序列化已有 | 部分；CLI mode 与 executor execution_mode 字段需统一 |
| 3 模型能力路由 | MoMA provider、路由、指标已有 | 部分；native 路径直接使用环境模型，缺统一决策证据 |
| 4 必要时动态组队 | TeamAgentSpec 实际构建 | 部分；plan 记录 single 不足以证明运行选择 single，需验证实际分支 |
| 5 修改与测试 | Git 发布、test runner 已有 | 未通过；native 不运行测试，路径约束未封闭 |
| 6 独立 Review | 类型与 gate helper 已有 | 未通过；native 忽略 Reviewer 响应，最终 verifier 缺失放行 |
| 7 创建 PR/MR | Provider 抽象与历史平台记录 | 部分；当前 GitHub CLI 装配报错，AtomGit 历史记录不等于当前回归 |
| 8 CI 与自动修复 | 聚合器、控制面、预算账本已有 | 部分；CLI 单次 reconcile，没有接通完整修复驱动与等待流程 |
| 9 Delivery Report | JSON/Markdown 与状态服务已有 | 部分；需与真正终态、证据一致，不能只靠打印完成 |
| 10 完整轨迹 | Capture/metrics/trajectory 组件已有 | 未签收；native 构造 traj 但未返回或持久化，verifier 只信元数据 |
| 11 Candidate 与离线评测 | miner/engine/gate 与 mock 测试已有 | 部分；缺当前同任务 Report→轨迹→候选→真实评测关联证据 |

## 关键偏差与优先级

### P0：错误放行与执行边界

1. **Native Review 硬编码批准**。`src/devopspilot/adapters/openjiuwen/executor.py` 的 `_execute_with_moma_native` 读取 rev_resp 后只累计 usage，不解析 verdict，直接构造 APPROVED；digest 使用 Python hash 而非 SHA-256。拒绝/非 JSON/空响应也可能继续提交。该路径未执行 test runner、行业 gate；文件写入直接拼接模型返回路径，缺绝对路径、父目录穿越、符号链接与允许目录限制。优先做统一 fail-closed 验证管线；在接通前显式禁用该自动 fallback。
2. **最终 verifier 不可信**。`orchestration/verifier.py` 缺 review 默认允许，不校验 published、CI SHA 与 review commit/digest 的一致性；trajectory 完整性仅检查字符串和数量。三个负向探针已复现，必须增加原始证据读取与一致性验证，不能依赖上游总是正确。
3. **已有幂等机制未被主入口使用**。`cli/main.py` live start 访问 `orchestrator._loop` 后手动 execute/save/open/reconcile，绕开 `DeliveryOrchestrator.start` 的 intent/lease。崩溃窗口、副作用重放仍需真实入口测试。
4. **可信配置传递断裂**。AppConfig 定义 require_review/test_command/required_checks/allowed_paths，但 assembly 未将其接入 task/workspace/执行器；executor 仅在 metadata 显式 true 时强制 Review/测试。字段存在不等于门禁生效。
5. **锁适配默认约束被绕过**。executor 无条件调用 `_patch_openjiuwen_lock_manager()`，该 wrapper 传 `force=True`；shim 对未知版本 None 也没有拒绝。导入时不改锁并不能证明执行时默认不改锁。必须验证真实 execute 的默认行为。
6. **凭据可能进入 Git 参数及错误**。assembly 将 token 放入 clone URL，workspace `_git` 异常包含完整参数。应改凭据注入方式并在日志、remote URL、报告做脱敏测试；本次未读取或输出凭据值，也未证明已发生外泄。

### P1：产品集成与证据缺口

- GitHub SCM/CI 构造签名错误；CLI 另调用 `get_issue` 而 Provider 实现为 `get_work_item`。采用公共契约装配，不再为入口维护平台特例流程。
- CLI 单次 reconcile 后即打印 completed/返回 0，即使还在 CHANGE_OPENED；明确“已受理/等待 CI/已验证/需人工”的状态与退出语义，接通持久化 CI 修复控制面。
- Planner 生成 mode 后仍无条件构造 TeamAgentSpec。需要实际 single/team 分支的行为证据，而不是仅测试 plan.mode。
- `demo deterministic` 是固定 print，未调用集成套件；`demo recorded` 是固定摘要；`demo live` 有凭据时只打印 starting 就返回。demo smoke 通过不能验收真实演示。
- `end-to-end-integration-suite` 使用 MockSCM、MockCI、直接生成代码和 Review，是有价值的确定性组件联测，不能支持 T22“三次真实交付”。
- T19 仅有 9 个 case；T20 comparator smoke 为手工数据。演示文档的 44.4%/88.9%/37.7% 没有在本次找到关联原始记录，现阶段应撤下实测与推荐结论，待证据补齐再恢复。
- 原计划 A0固定单模型/A1路由单Agent/A2路由Team/A3加进化，与 comparator 的轻量/强模型/动态单Agent/Team 不同。建议后者改名 R0–R3 作路由诊断，保留 A0–A3 验证 PRD 的进化增益，避免同名异义。
- 40 项脚本 runner 未覆盖新增 pytest 文件；`.venv` 无 pytest；CI 安装未使用现有 lock 文件。依赖、环境、测试收集仍需闭合。

## 根因判断

主要偏差是**组件测试完成被提升成产品验收完成**，再叠加新增 native/CLI 支路复用了展示与状态，却绕开原有安全与恢复契约。目录分层总体合理，不建议重写 Core 或引入新框架。纠偏应统一“配置→编排→执行→验证→证据”路径，让 demo、CLI、测试调用同一实现。

已有 T01–T25 的实现成果保留，但完成勾选不再作为验收事实。旧阶段计划归档，后续以新的 IMPLEMENTATION_PLAN 和下述签收门槛为准。

## 后续节奏与验收门槛

顺序：恢复可信基线 → 关闭错误放行 → 接通唯一主链 → 有效评测与真实 RC 验收。详细责任、测试和依赖见根目录 IMPLEMENTATION_PLAN.md。

估算 **16–24 人日**（一名熟悉 Python/Agent/CI 的工程师；模型配额、平台审批等待另计），Stage 1 后校准。先 GitHub 主线；AtomGit 保留已知能力边界，作为后续第二平台验证。不扩重型 Web/IAM、工业医疗包或更多进化类型。

完成门槛：当前候选 SHA 在干净环境离线全绿；所有 P0 负向行为被阻断；同一 CLI 连续三次独立 Live 交付（至少一次红→自动修复→绿、另有中断恢复）；11 项证据可按 task/run/SHA 串联；评测原始数据可重算；候选保持 PENDING_HUMAN 直到真实批准。验证失败不能通过降低门禁或改写成功定义解决。

## 补充：意图分类专项

[意图分类评估](intent-assessment-2026-09-28.md) 已复现标题覆盖正文、否定与英文子串误判、显式意图被模型覆盖和非法枚举接受。列入 Stage 2 的副作用门禁及 Stage 3 的入口收敛。
