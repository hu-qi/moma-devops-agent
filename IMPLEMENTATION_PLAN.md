# DevOpsPilot V1 收敛实施计划

依据：[2026-09-26 评估](docs/project-assessment-2026-09-26.md)、`PRD/00-decisions.md`、`PRD/02-v1-scope.md`。

目标：完成可稳定复现和恢复的研发交付 V1。保持 Core / Runtime / MaaS / SCM 分层，不重写已有 Provider 与状态契约。详细工作项见 [TODO.md](TODO.md)。

本次只完成评估、证据纠正与计划编制，以下实施阶段均未完成。预计单名熟悉 Python/CI 的工程师投入 **20–30 人日**；不包含审批等待、外部账号开通和模型服务不稳定时间。估算需在 Stage 1 后按依赖与 Runtime 结果校准，不是交付承诺。

## Stage 1: 建立可复现基线并恢复演示夹具
**Goal**: 从任意干净环境完成离线检查，并可靠准备和重置 live fixture；统一依赖与证据口径。
**Success Criteria**: 一条安装命令、一条离线检查命令；所有选定 Smoke 和三个指标脚本通过；industry-pack 依赖有声明；E2E 不依赖偶然存在的分支；文档分别标注 mock/live/历史成功/当前失败。
**Tests**: 干净 Python 3.11 环境安装；3 个 fixture precondition；现有 15 个 Smoke；3 个直接执行指标脚本；fixture 分支不存在/存在/重复初始化/并发申请同 fixture 的测试。
**Status**: Not Started

- 时间：2–3 人日。责任：工程基础/CI。任务：T01–T04。
- 增加项目安装元数据与稳定版本约束。Runtime release 分支引用应解析为已验证 commit；区分离线 core、runtime、industry 可选依赖，禁止默默依赖开发机全局环境。
- 建立统一离线检查入口，复用现有 main/assert 测试。正常回归不能直接收集“故意失败”的 benchmark 原始 fixture。
- Fixture bootstrap/reset 有明确目标仓库、基准 SHA、隔离命名与清理策略；将 reset → E2E 的依赖显式编排，避免互相删除或 reset 同一共享分支。
- Live 任务单独按需运行；普通 PR 的离线检查无需模型凭据，不自动消耗模型额度。
- 出口：安装、检查、fixture 准备说明可由第二个干净环境复现；失败证据可以定位到具体阶段。

## Stage 2: 封闭交付正确性与 Runtime 门禁
**Goal**: 让发布与最终通过由结构化证据决定，并消除全局关闭锁作为默认行为。
**Success Criteria**: Reviewer 结果与 diff/提交绑定；拒绝、缺失或陈旧 review 阻断交付；required CI 完整聚合；必要测试不可为空且有超时；Runtime 降级与证据缺失不能被报告为完整成功。
**Tests**: Review APPROVE/REJECT/缺失/超时/过期；CI green+red、缺 required check、无关 workflow、旧 SHA、旧 attempt、仍在运行、分页；测试命令缺失/超时/产生子进程；双任务文件写竞争、取消、shutdown 后无残留任务；捕获失败与空轨迹。
**Status**: Not Started

- 时间：4–6 人日。责任：执行器/验证。依赖：Stage 1；任务：T05–T09。
- 在 contracts 增加可序列化 ReviewResult 和 VerificationEvidence；Review 只读能力限制、独立身份与最终 diff digest 一并记录。若测试会修改源码，重新验证/Review 最终内容，不能沿用旧结论。
- required checks 由可信项目配置给出；Provider 返回 workflow/check identity、commit、attempt 等足够元数据，Core 做聚合。缺检查维持 pending 或明确超时升级，不能跳过。
- 测试与工具执行增加超时、取消、资源和凭据边界；工作目录不是安全沙箱，禁止将“cwd 位于 workspace”当成文件/网络权限隔离。
- 为 Runtime 建最小重现；先尝试已验证版本组合或上游修复，其次独立进程隔离。临时 shim 必须受版本白名单与显式开关控制，不能 import 时修改全局锁；默认不关闭锁。
- 统一 success / degraded / evidence-incomplete 状态。模型完成动作、业务 oracle 成功、完整交付验收三个结果分别存储。
- 出口：所有负向案例都阻断发布或 verified；无需连接真实平台即可证明门禁正确。

## Stage 3: 统一入口与可恢复交付
**Goal**: 用一个产品入口调用现有组件，实现事件去重、执行前记账、恢复，以及 Single Agent First。
**Success Criteria**: CLI 支持 start/status/resume/report；同任务/事件重放不重复远端副作用；失败执行消耗预算；Plan 可审阅；简单任务采用单实施 Agent、复杂任务采用 Team，两者均独立 Review。
**Tests**: 相同 delivery/event 重放；两个 worker 竞争；执行前、push 后、PR 后、ledger 后和 state save 前中断；超时租约；执行失败记账；达到预算升级人工；plan/pack 序列化向后兼容；单 Agent 与 Team 行为对照。
**Status**: Not Started

- 时间：5–7 人日。责任：编排/持久化。依赖：Stage 2；任务：T10–T15。
- 使用现有 SQLite 增加 operation intent、唯一幂等键、lease、attempt 状态与预算预留；不要在远端网络调用期间持有长数据库事务。
- Intent → 外部执行 → 结果记账；恢复先核查远端 branch SHA / PR / CI attempt 再续跑。保留 at-least-once 事件消费与幂等副作用的实际语义，不承诺跨服务 exactly-once。
- 最小 gateway 先以 CLI 的显式事件/任务输入实现，复用 normalize contract；Webhook HTTP 服务可后续接入，不为 V1 引入完整 IAM 或后台。
- 执行计划包含目标、上下文来源、可改路径、测试命令、风险、模式/路由理由、预算与人工门禁；配置与 Issue 文本的权限分离。
- 将 E2E 内报告/轮询/状态拼装抽成可复用服务，使 E2E 成为产品入口的测试，避免 E2E 实现第二套业务链路。
- 出口：从 CLI 完整走到 Report；中断恢复不重新开始整个 Agent 流程；副作用计数可审计。

## Stage 4: 行业门禁与有效评测
**Goal**: 做深一个行业场景，并完成三类 oracle、四组消融和最小 Evolution 离线闭环。
**Success Criteria**: Pack 贯穿启动/保存/恢复/修复；gate 检查真实候选代码；三类任务可量化评测；A0–A3 同题同环境记录结果；candidate 有来源轨迹与离线报告，正式激活保持真实人工审批。
**Tests**: Pack 未知版本/非法配置/缺失依赖显式失败；持久化与修复保留 digest；违规代码失败、修复通过、改坏回归失败；结构化 Review 标注集 precision/recall；baseline/candidate 固定 holdout；负增益候选拒绝；合成审批不能替代真实提案审批。
**Status**: Not Started

- 时间：6–9 人日。责任：行业规则/评测。依赖：Stage 3；任务：T16–T21。
- 默认以政务“审计/脱敏”作为首个候选演示方向，先核实案例可得性再冻结；金融包保留参考状态，不同时扩工业与医疗。
- 行业 Pack 用类型化引用及不可变版本/digest；设计迁移兼容，既支持旧 state，也不能在 pack 缺失时静默继续。
- 规则标注标准来源、具体版本、适用条件、权威性与工程建议属性；真实规范核验独立完成，示例不宣称合规认证。
- 实现 Review oracle，再从 3 扩到 9 个有效 case 做工程验收，最终扩到 PRD 目标 20–30。按源任务族分离训练/开发和 holdout，防相近题泄漏。
- A0 固定模型+单 Agent，A1 MoMA 路由+单 Agent，A2 MoMA+Team，A3 加候选进化。固定任务、环境与预算，建议每组每题至少 3 次；先报告描述统计，不凭少量样本宣称显著收益。
- Candidate 只选一种 Skill/Prompt 对象；未获人工审批时只输出 PENDING_HUMAN，不以验收为理由自动激活。
- 出口：行业 gate 可检出真实缺陷，Bench 原始数据可复算，进化有可追溯来源并如实接受或拒绝候选。

## Stage 5: V1 发布候选验收与演示材料
**Goal**: 验证一个能交给他人复现的 V1 发布候选，并形成真实证据驱动的 Demo。
**Success Criteria**: 干净环境可安装；连续 3 次独立真实交付成功，至少一次包含 CI 自动修复；每次有 Plan、路由、Review、diff、CI、Report、Trajectory 与 candidate/eval 关联；现有生产 Skill 未被未审批候选覆盖。
**Tests**: 完整 CLI live E2E；fixture 重置后重复运行；进程终止后 resume；无模型额度/权限不足/CI 延迟升级人工；回归门禁；证据文件脱敏与链接检查；录屏与 live 结果一致。
**Status**: Not Started

- 时间：3–5 人日。责任：交付验收。依赖：Stage 4；任务：T22–T25。
- 从同一 commit 固定依赖、fixture 版本与 case 版本，保存原始结果及可读验收表。
- 不将历史 success 或其他 SHA 的 CI 用作当前未提交实现的验收。
- 准备 live / recorded / deterministic 三条演示路径；断网降级时明确展示历史记录，不伪装实时成功。
- 国产平台真实验证为后续扩展 T25，是否纳入本阶段取决于凭据和官方契约确认；不阻塞 GitHub 主线 V1，不能把 mock 叫作 native live 支持。
- 出口：逐条签收 PRD 的 11 个成功标准。所有阶段完成后按项目规则移除本文件，保留评估、TODO 和最终验收报告作为历史记录。

## 执行约束

- 每个任务先建立失败案例，再做最小实现，运行受影响的离线测试与必要集成检查，按独立可工作的变更提交。
- 同一问题连续 3 次失败后停止重复尝试，记录具体错误、调研替代方案并重新拆解；不通过放宽质量门禁消除失败。
- 不合并/清理评估前已有的未提交代码；先明确其依赖与验收，再拆成可审查提交。
- 只有新变更或新失败理由才重复扩大测试，避免用大量绿色小测试替代完整主链验证。
