# DevOpsPilot 完成度与方向评估

评估日期：2026-09-26。基线：`abcb3895988a64d66e690042ff73ac5a82a3bb6c`，加评估开始时已有的本地修改与未跟踪 Industry Pack / AtomGit 实现。

## 结论

**产品方向仍与 PRD 一致，但实施重心已出现偏移：应从持续增加实验、平台适配和进化分支，转为完成一条可复现、可恢复、有强制质量门禁的交付主链。**

当前是“核心技术验证中后期、V1 集成收敛前期”。不能按源码文件数、Smoke 数量或一次绿色 CI 宣称产品完成，也无需推倒重写。Provider / Contracts 分层、独立 Git 发布、轨迹、修复预算、进化审批与注册表均值得保留。

按下述 11 项验收要求，已有不少局部证据，但尚无同一次运行覆盖全部要求的稳定产品验收证据。本报告不把局部验证换算成看似精确的百分比。

本轮纠正范围为状态、证据口径、开发顺序和实施计划；发现的运行时代码缺陷列入 TODO，未混入现有未提交业务改动。未触发模型请求、远端写入、部署或 CI 重跑。

## 1. 完成度矩阵

依据 `PRD/02-v1-scope.md` 的 11 条成功标准。这里“有真实证据”只表示对应场景曾运行成功，不表示通用可靠性。

| V1 要求 | 当前状态 | 证据与欠缺 |
|---|---|---|
| 理解 Issue 与仓库上下文 | 部分完成 | SCM WorkItem 与隔离 workspace 已有；输入主要是 Issue 文本、路径、测试命令，缺统一入口与可审阅上下文产物 |
| 可解释执行计划 | 部分完成 | Leader 提示词要求规划；缺独立持久化 Plan、任务依赖和执行模式决策产物 |
| 按任务选择模型 | 已有实现及历史运行证据 | profiler/router/role planner 和 MoMA 适配存在；尚无完整 A0–A3 同题对照证明收益 |
| 必要时动态组队 | 部分完成、偏离 D-004 | Specialist 由 Leader 调用，但生产 executor 固定走 TeamAgentSpec，缺可选的单 Agent 主执行路径 |
| 修改代码并测试 | 已有受控 fixture 真实证据 | 本地路径校验、独立测试、提交和发布已实现；命令可为空、测试超时与执行隔离边界仍需收紧 |
| 独立 Reviewer 验证 | 部分完成、缺硬门禁 | 提示词要求 Review；executor 未把结构化 reviewer verdict、独立身份、diff/commit 绑定作为提交条件 |
| 创建 PR/MR | GitHub 已有真实证据 | Provider 化方向正确；CNB/AtomGit mock 不能替代真实平台验证，其他平台无需抢先扩展 |
| CI 失败 RCA / 修复 | 真实跑通过、复现不稳定 | 同分支修复 E2E 有 success；随后同 SHA 的运行因 fixture 分支不存在在 checkout 失败 |
| Delivery Report | 部分完成 | 报告主要由 E2E 脚本拼接/发送；缺统一报告服务与证据完整性判定 |
| 完整 Trajectory | 部分完成 | 有 canonical capture、metrics、bridge；超时可降级为空轨迹，不能据此宣称“完整” |
| Candidate 与离线评测 | 机制已有、产品集成未闭环 | gate/audit/registry 和实验存在；真实提案保持待审批，合成审批仅验证机制，不能当成生产晋级或稳定收益 |

产品交付缺口还包括：没有根目录依赖清单/锁定文件和统一 CLI，缺可靠事件消费与恢复路径；Industry Pack 未形成真正的目标仓库质量门禁；Bench 仅 3 个案例且 structured-review evaluator 未完成。

## 2. 本次实测

机器可读的本轮检查摘要：[evidence/project-assessment-2026-09-26.json](evidence/project-assessment-2026-09-26.json)。记录的是检查结果与边界，不包含凭据或完整远端日志。

### 本地验证

在临时目录复制源码、实验和 fixture，以项目 `.venv/bin/python`（3.11.14）执行，避免实验产物混入工作区：

- 15 个选定 Smoke：**14 通过，1 因缺依赖未能运行**。
- 通过项：provider-contract、model-routing、trajectory、delivery-loop、delivery-state-store、durable-delivery、git-publisher、delivery-pipeline、autonomous-control-plane、remediation-adapter、evolution-gate、GitHub/CNB/AtomGit reference adapter。
- Industry Pack Smoke：`ModuleNotFoundError: No module named 'yaml'`。说明当前环境不可直接复现，不等于所有 pack 逻辑均错误；项目未提供统一依赖安装基线。
- `validate-fixtures`：3/3 通过，仅证明故障初始态成立，**不是 Agent 成功率 100%**。
- 直接执行 `test_profiler.py`、trajectory `test_metrics.py`、bench `test_runtime_metrics.py`：3/3 通过。它们采用 `main()` 断言脚本；本环境没有 pytest，不能把未运行的 pytest 记成完整测试套件通过。
- 这不是所有实验的全量回归；没有执行收费模型、外部写入和 live E2E。

另外用现有 FakeSCM / FakeCI 与 SQLite 做了针对性探测：

| 探测 | 实际结果 | 影响 |
|---|---|---|
| 相同 delivery_id 连续 start 两次 | 第二次报 `DeliveryStateConflict`，但 FakeSCM 的 comment 已有 2 次 | 幂等检查发生在执行、发布、创建 PR/评论之后，冲突不能防重复副作用 |
| 一条 green + 一条 failed CI | `ci-passed` | 当前只读 `runs[0]`，缺 required checks 聚合策略 |
| 含 industry_pack 的 state 存取 | 恢复后 `industry_pack=None` | 重启后行业约束消失 |
| `typing.get_type_hints(DeliveryTask)` | `NameError: name 'Any' is not defined` | 新字段使用未导入的 Any；延迟注解使普通 import 暂未暴露问题 |

首轮 CI 探测曾因漏传 FakeCI 要求的 commit_sha 参数触发 fixture 断言；补全参数后复现上表结果。不存在据失败探测推断产品缺陷的情况。

### 远端证据

使用 `gh run list/view` 只读核对：

- [CI 修复 E2E 成功运行 36086881849](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086881849)：与当前 HEAD 相同 SHA，日志包含同分支 push、CI recovered、verified 标记；但也明确记录 `DEVOPSPILOT_RUNTIME_DEGRADED=agentteam_timeout timeout_seconds=240.0`。证明已有真实业务成功路径，同时 Runtime 正常终止仍未解决。
- [随后失败运行 36086892725](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086892725)：同 SHA，checkout 报 `A branch or tag with the name 'devopspilot/fixture-ci-remediation' could not be found`，模型及修复步骤均 skipped。**这是 fixture 准备/调度问题，不能归因于本次模型推理失败。**
- [Fixture CI 36087239486](https://github.com/hu-qi/moma-devops-agent/actions/runs/36087239486) 成功，而 [Fixture Reset 36087239543](https://github.com/hu-qi/moma-devops-agent/actions/runs/36087239543) 失败；本轮未深入该 reset run 的失败根因，不作进一步归因。
- `docs/research/18-first-live-github-delivery-e2e.md` 记录首次交付曾需外部 SCM control plane 补建 PR，且 Team 超时。因此该历史样例不是完全无人工介入、Runtime 健康的证据。

结论应表述为：**GitHub 受控修复流程已有成功证据，但 fixture 生命周期和统一验收尚未稳定。**

## 3. 偏差、根因和修正

### P0：发布前质量门禁不完整

`src/devopspilot/adapters/openjiuwen/executor.py` 的 Review 要求主要在提示词中；后续代码检查 diff、路径、可选 test_command 后提交，没有读取和强制执行 reviewer verdict。Reviewer REJECT、缺失或超时不可只依靠 Leader 自觉处理。

`orchestration/delivery_loop.py::reconcile_ci` 只采用第一条 CI 结果。应按精确提交身份、配置的 required workflows/checks 和最新 attempt 聚合；缺少任何 required check 时保持 pending，失败时禁止 verified。具体 required 集合必须由项目可信配置指定，不能简单要求仓库所有不相关 workflow 都绿。

修正：新增结构化 ReviewResult 与统一 DeliveryVerifier，绑定实际被评审 diff/提交；增加负向门禁测试。业务成功、运行时健康、证据完整性分别记账。

### P0：持久化不等于可恢复、幂等

`orchestration/service.py::start` 在整个 `loop.start` 完成后才 save；`control_plane.py` 在重试 CI 或 remediator 完成后才 append ledger。发生重复投递、并发或“已 push、未记账”崩溃时，数据库版本冲突不足以避免重复副作用，失败尝试也可能未消耗预算。

修正：执行前持久化任务/操作 intent 和预算预留；用 delivery/event/run/attempt 唯一键与 lease 管理执行权；执行后记录结果。重启时先 reconcile 远端已发生的副作用，再决定是否补偿或重试。不能用一个跨网络长事务假装 exactly-once。

### P0：Runtime 修复方式过宽

executor 导入时调用 `_patch_openjiuwen_lock_manager`，直接把第三方私有模块的多层读写锁改成 no-op，并吞掉异常。单进程并不意味着同一进程内没有并发任务；当前隔离假设也不是产品级强制约束。

修正：先固定可复现依赖，提取最小生命周期用例，优先兼容版本/上游修复/独立进程边界；确需临时 shim 时限定版本与开关、默认 fail closed，显式记录启用状态，验证并发写与 shutdown。不得把关闭同步机制记成长期完成项。

### P1：行业规则停在提示词，门禁尚未成立

- `industry/loader.py::build_industry_context` 没有加入 test_gates；executor 没有通用 Pack Gate runner。
- 政务 gate 只打印 PASS；金融 gate 只验证 Python Decimal 常量表达式，不检查目标仓库变更。
- `DeliveryLoop.start` 未接入 pack 选择；`sqlite_state.py` 存取不包含 pack；remediation 重建 DeliveryTask 也未带回 pack。
- 行业上下文导入失败被 `except Exception: pass` 忽略，可能无声丢失规则。

修正：先选一个行业和一个能执行的工程要求，例如政务审计字段/日志脱敏，建立会失败的目标仓库样例和修复后的通过样例；固定 pack id/version/digest，贯穿启动、持久化、恢复、修复与最终报告。标准条文须另行核验来源、版本、适用范围；本次仅审代码，不对现有标准映射作合规背书。

### P1：Single Agent First 尚未兑现

profile 已计算 complexity/risk，但 executor 主路径仍固定创建 AgentTeam。简单 bug 同样承担 Leader/Coding/Review 的多轮成本与 lifecycle 风险。

修正：增加 ExecutionPlan / ExecutionMode，低复杂度任务走单个实施 Agent，独立 Reviewer 作为交付门禁；复杂任务才组 Team。保留可解释决策与人为覆盖，不用未经测量的分数阈值冒充最优策略。

### P1：评测增长慢于功能增长

DevOpsBench 只有 coding/review/ci-debug 各 1 个 case；`runner.py` 的 structured-review evaluator 明确抛 NotImplementedError。角色模型比较或单一 Team Pattern A/B 不等于 PRD D-008 的四组消融。

修正：先完成三类 oracle 和 A0–A3 同题可比执行，再逐步扩至 20–30 个案例；固定 holdout，记录重复次数、失败原因、人工介入、tokens、耗时、运行时健康。缺价格时 cost 保持未知，不填 0；候选没收益则保留基线。

### P2：多平台与进化支线超前

AtomGit Smoke 使用 `FakeAtomGitClient`，只能证明本地契约与实现相互一致；没有证据证明其 endpoint、签名和 Actions 语义符合真实平台。CNB 同样需标明 mock 与 live 边界。先稳定 GitHub 主线，再选择一个国产平台完成真实纵向闭环。

Evolution gate/audit/registry 有价值，但继续扩充 Swarm Skill 类型不能替代主链可用性。近期只保留一种 Skill/Prompt candidate 完成离线验证和人工审批边界；真实 proposal 的 PENDING_HUMAN 状态不得由合成审批替代。

## 4. 纠偏后的交付边界

最小产品是：**一个 CLI 入口、一个稳定 SCM、一个可执行行业例子、三类有效评测、一条完整且能恢复的交付主链。**

链路：Task → 持久化 Plan → Single/Team → 独立 Review → 测试/行业 Gate → Commit/Publish → PR → required CI 聚合 → 有界修复 → Final Verify → Report/Trajectory → 离线 Candidate。

在主链验收前暂缓：新增第三/第四行业包、六平台同时完善、重型 Web 后台、自动部署、多种新进化对象。保留已有代码，不删除未完成探索。

详细任务与完成条件见根目录 [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md) 与 [TODO.md](../TODO.md)。

## 5. 最终验收标准

1. 新环境按文档安装，无手动 PYTHONPATH 拼装和临时依赖补丁即可运行统一入口。
2. 同一 Issue 可连续完成 3 次独立重置的真实交付；包括至少一次真实 CI 红→修复→绿，各自产出完整证据。
3. 人工中断后 resume 不重复创建 PR、重复计费执行或无条件再次 push；每个副作用边界有故障注入测试。
4. Reviewer REJECT/缺失、required check 失败/缺失、必需行业 gate 失败、提交身份不一致均阻断 verified。
5. 单 Agent / Team 两条分支可解释，报告清楚标记 degraded runtime 与人工介入。
6. 至少三类 oracle 有效，最终目标 20–30 个版本化 case，A0–A3 有原始结果与 holdout，无收益时如实拒绝候选。
7. 一个真实轨迹可追溯到 candidate 与离线评测；正式晋级必须等待真实人工审批，不以测试审批替代。
