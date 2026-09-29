# DevOpsPilot 评审专家快速指引与证据核验指南 (C28)

本文档专为**移动云杯专家评审委员会**准备，旨在以最短时间（3～5 分钟）帮助评审专家掌握 DevOpsPilot 的核心创新、完成本地一键复现，并依据 PRD 11 条核心成功指标进行逐项证据核验。

---

## 1. 评审速览与核心创新点

DevOpsPilot 是面向研发自主演进的端到端自动化交付控制面。针对市面上 AI 编程工具“缺乏交付安全门禁、模型调用成本失控、多智能体协同易生幻觉与死循环”三大行业顽疾，本项目实现四项突破：

1. **Single Agent First 原则**：绝不盲目堆砌多智能体。低风险与单模块任务默认采用单 Agent 经济档，仅在复杂架构变更时调度 Team 协同，拒绝多智能体虚假繁荣。
2. **强制独立代码审查硬门禁 (Enforced Independent Review)**：生成代码与审查逻辑物理隔离。无论单 Agent 还是 Team，均须独立 Reviewer 签署 `APPROVED` 与数字摘要校验，彻底杜绝“自写自审”。
3. **意图租约与预算前置预留 (Idempotency & Pre-reservation)**：外部副作用（PR 创建、Commit 推送）前完成原子持久化租约与重试预算扣减，中断恢复（resume）零重复 PR、零死循环。
4. **移动云 MoMA 价格透明与受控自演进**：全量对齐移动云官方自营模型资费，基准评测同题同预算可复算；自演进候选默认严格停留在 `PENDING_HUMAN`，严禁未经审批私自篡改生产策略。

---

## 2. 3 分钟极速复现路径 (Fast-Track Reproduction)

评审专家无需准备复杂的外部云账号与 API Key，在纯本地干净环境即可通过统一脚本验证全部交付主链：

### 步骤 1：获取代码并执行一键环境验证
```bash
git clone https://github.com/hu-qi/moma-devops-agent.git
cd moma-devops-agent

# 执行全量 41 项离线测试套件（预期全绿，耗时约 12 秒）
python3 scripts/run_offline_checks.py
```

### 步骤 2：运行确定性端到端交付演示
```bash
# 启动本地隔离 Git 仓库与完整控制面交付流转（零外部网络依赖，耗时约 5 秒）
./scripts/run_demo.sh deterministic
```
**专家观察要点**：
- 控制台将展示完整 3 轮独立运行：
  1. `Standard Feature Delivery`（特性编码、模型路由、Review 审查与 PR 开启）
  2. `Autonomous CI Remediation`（CI 模拟红灯、自动捕获日志、生成 RCA 并在同分支精准修复翻绿）
  3. `Industry Compliance Pack`（政务合规包拦截明文敏感数据，强制要求脱敏处理）

### 步骤 3：查看历史真实证据归档
```bash
./scripts/run_demo.sh recorded
```
**专家观察要点**：
- 检视保存在 `docs/evidence/` 下的真实平台运行日志、SQLite 状态数据库及审计摘要。

---

## 3. PRD 11 条成功标准逐项核验表 (Verification Matrix)

评审专家可依据下表，查验代码实现位置与对应的自动化测试验证断言：

| # | PRD 规格要求 | 核心实现文件 | 自动化验证用例 / 运行脚本 | 证据类型 |
|---|---|---|---|---|
| **1** | 正确理解任务与仓库上下文 | `src/devopspilot/cli/main.py`<br>`src/devopspilot/scm/` | `tests/test_cli_smoke.py`<br>`experiments/cli-smoke/main.py` | 确定性代码 + 集成测试 |
| **2** | 形成可解释执行计划 | `src/devopspilot/orchestration/planner.py` | `experiments/end-to-end-integration-suite/` (Run 1) | 执行日志与 Plan 快照 |
| **3** | 根据任务选择模型能力档 | `src/devopspilot/adapters/moma/`<br>`src/devopspilot/orchestration/` | `benchmarks/devopsbench/runner.py`<br>`docs/competition/stage3-rc-manifest.md` | MoMA 官方价格与路由决策 |
| **4** | 必要时动态组建 AgentTeam | `src/devopspilot/adapters/openjiuwen/executor.py` | `tests/test_path_policy_and_review.py` | 单/多 Agent 动态分支 |
| **5** | 完成代码修改与隔离测试 | `src/devopspilot/orchestration/path_policy.py` | `tests/test_path_policy_and_review.py` | 路径白名单防逃逸断言 |
| **6** | 独立 Reviewer 强制验证 | `src/devopspilot/orchestration/verifier.py` | `tests/test_path_policy_and_review.py` | 缺失/REJECT 阻断断言 |
| **7** | 创建规范 Pull Request | `src/devopspilot/scm/github.py`<br>`src/devopspilot/scm/atomgit.py` | `experiments/end-to-end-integration-suite/` | PR 打开与状态流转 |
| **8** | CI 结果 + 失败自动同分支修复 | `src/devopspilot/orchestration/service.py` | `experiments/end-to-end-integration-suite/` (Run 2) | 红转绿 RCA 追加 Commit |
| **9** | 输出标准 Delivery Report | `src/devopspilot/cli/main.py` (`report` 子命令) | `tests/test_cli_smoke.py` | JSON / Markdown 报告 |
| **10** | 持久化完整 Trajectory | `src/devopspilot/trajectory/persistent_store.py` | `tests/test_trajectory_evidence.py` | 磁盘文件与摘要核验 |
| **11** | 离线评测与受控进化候选 | `src/devopspilot/evolution/engine.py` | `experiments/governed-evolution-smoke/main.py` | 负收益阻断、PENDING_HUMAN、回滚 |

---

## 4. 系统局限性与已知工程边界 (Boundaries & Limitations)

为了秉持严谨求实的科学态度，我们主动向评审专家公开本系统的工程边界：

1. **平台 CI 边界（GitHub vs AtomGit）**：
   - **GitHub 主线**：支持完整的 GitHub Actions Checks 状态轮询、失败日志抓取与 CI 红灯自动修复链路。
   - **AtomGit 边界**：经实测，AtomGit 原生平台目前未开放公有云的 Actions 运行能力。因此对于 AtomGit 适配，系统采用 **Webhook-Only / 外部 CI 驱动** 边界（详见 `docs/competition/stage3-ci-boundaries.md`），绝不伪造不存在的原生云端运行记录。
2. **离线退避与网络波动保障**：
   - 当外部平台（GitHub API、MoMA 网关）因网络波动、鉴权凭据未就绪或额度耗尽时，系统支持通过 `--mode deterministic` 无缝降级至本地确定性演练，核心状态机与门禁逻辑与线上完全一致。
3. **行业合规包规范定位**：
   - 当前内置的政务合规包（`industry-packs/government`）实现了结构化敏感数据脱敏、合规注释与危险配置拦截规则，设计作为工程质量门禁示范，并非国家法律资质认证。
4. **模型定价与商业估算说明**：
   - 所有模型调用计费均严格对齐中国移动官方文档（`ecloud.10086.cn` 文档编号 91592），未在官方价目表中核实的模型一律标记为 `Unestimated`，绝不虚构 0 元或免费，确保成本效益对比客观真实。
