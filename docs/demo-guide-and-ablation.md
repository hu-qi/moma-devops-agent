> **2026-09-28 验收更新**：CLI `demo` 命令已完成产品级重构（Deterministic 模式驱动底层 3 轮完整独立交付套件，Recorded 模式基于已归档真实轨迹，Live 模式直通正式交付入口）。消融对照表历史数据待全量基准重跑后更新。详见 [项目评估](project-assessment-2026-09-28.md)。

# DevOpsPilot V1 演示体系与四组消融对照文档

本文档为评审专家、开发者与外部复现人员提供完整的操作指南、系统架构说明、三条演示路径（Live / Recorded / Deterministic Fallback），以及 **A0 / A1 / A2 / A3 模型路由与单/多 Agent 成本效益对照表**。

---

## 1. 核心架构与设计原则

DevOpsPilot 是面向研发自主演进的端到端自动化交付控制面，遵循以下核心工程原则：
1. **Single Agent First**：常规修复与低风险任务默认优先调度 Single Agent；仅在跨文件架构重构、高推理复杂度或高风险任务时才启用 Agent Team；无显著净收益不推广 Team。
2. **强制独立代码审查 (Enforced Independent Review)**：无论 Single Agent 还是 Agent Team 生成的代码，必须经过独立的 Reviewer 严格复审并签发 `APPROVED`，杜绝“自写自审”。
3. **租约控制与预算前置预留 (Idempotency & Pre-reservation)**：在触发外部副作用（创建 PR、修改代码、推送 Commit）前，必须先行原子持久化意图租约并在记账表中预留修复 Attempt，防止进程崩溃导致无界循环或重试计数丢失。
4. **全生命周期可观测性 (Evidence Completeness)**：每次交付必须完整持久化执行计划 (Plan)、模型配置、代码审查快照、CI 日志分析、环境指纹、真实 Commit SHA 与轨迹事件 (Trajectory)。

---

## 2. 三条演示路径 (Demonstration Pathways)

为了应对不同评审与答辩网络环境，DevOpsPilot 提供 3 条互为备份的独立演示路径：

### 路径 A：Deterministic Fallback（确定性离线演示，零模型成本）
- **适用场景**：答辩现场断网、无外部模型 API 额度、快速回归验收。
- **特点**：全离线确定性执行，本地拉起隔离的真实 Git 仓库与本地裸远端仓库，模拟完整的 Single Agent 规划、代码生成、独立审查、受控行业门禁与 CI 绿灯闭环。
- **执行命令**：
  ```bash
  devopspilot demo --mode deterministic
  # 或直接运行底层集成套件:
  python experiments/end-to-end-integration-suite/main.py
  ```
- **输出产物**：控制台输出完整的交付状态流转，生成标准 JSON 与 Markdown 格式的交付验收报告。

### 路径 B：Recorded Trajectory（真实录屏与历史轨迹回放）
- **适用场景**：离线检视真实外部平台操作链路、确认平台交互真实性。
- **特点**：直接索引并重现我们在 GitHub Live 环境下执行真实 CI 自动修复所沉淀的结构化历史记录。
- **执行命令**：
  ```bash
  devopspilot demo --mode recorded
  ```
- **真实证据记录**：
  - **Run ID**: `36086881849` ([GitHub Actions 运行链接](https://github.com/hu-qi/moma-devops-agent/actions/runs/36086881849))
  - **交付 SHA**: `13034d6`
  - **降级标记**: 真实记录 `agentteam_timeout 240s`（按事实披露，绝不虚构完美）
  - **成效**: 成功抓取 broken CI 报错日志，自动生成针对性修复 commit，推送到同分支后触发二次 CI 转绿。

### 路径 C：Live E2E Execution（线上真实端到端执行）
- **适用场景**：具备稳定公网访问与 GitHub/MoMA Token 时的实时交互演练。
- **前置依赖**：
  ```bash
  export GITHUB_TOKEN="ghp_xxxx"
  export MOMA_API_KEY="moma_xxxx"
  export MOMA_BASE_URL="https://api.moma.example.com/v1"
  ```
- **执行命令**：
  ```bash
  devopspilot start --repo hu-qi/moma-devops-agent --issue 1 --target-branch main
  ```
- **保护策略**：若环境缺少上述 Token，系统会安全拦截并引导回退至 Deterministic 模式，绝不发生死锁或无凭证静默报错。

---

## 3. A0 / A1 / A2 / A3 模型路由与成本效益消融对照表

我们在同题（DevOpsBench 统一基准用例集：包含 Coding、Code-Review、CI-Debug 三类真实任务）、同预算（超时时间 60s，最大重试 3 次）的标准测试环境下，对 4 组策略进行了严格的对照评测：

### 策略定义
- **A0 (Single Fast)**: 单一快速轻量模型（如 deepseek-v3 / gpt-4o-mini），单 Agent 实施。
- **A1 (Single Capable)**: 单一推理强模型（如 deepseek-r1 / claude-3-5-sonnet），单 Agent 实施。
- **A2 (Dynamic Single)**: 根据任务上下文复杂度动态路由（简单用 Fast，复杂用 Capable），单 Agent 实施（践行 Single Agent First）。
- **A3 (Agent Team)**: 完整多角色团队协作（Architect 拆解 + Coder 实施 + Independent Reviewer 审查），多 Agent Team。

### 对照数据表 (Benchmark Comparison Matrix)

> **⚠️ 数据状态：未验证（UNVERIFIED）** — 依据 [2026-09-28 项目评估](project-assessment-2026-09-28.md) C03/T20 结论：下表数值（44.4% / 88.9% / 37.7% 等）在本次评估中**未找到关联的原始运行记录**，现阶段**撤下实测与推荐结论**。表中数据保留仅供历史参照，不得用于发布验收或对外宣传；待 C10（评测集扩到 20–30 例、provenance 可追溯、原始结果可重算）完成后，以可复算证据重新填列。

| 策略编号 | 策略名称与架构 | 任务成功率 (Pass Rate) | 平均耗时 (Avg Duration) | 总 Token 消耗 (Tokens) | 估算模型费用 (Estimated Cost) | 人工介入数 (Interventions) | 主要失败原因分布 | 决策裁决与推荐建议 |
|---|---|---|---|---|---|---|---|---|
| **A0** | Single Fast<br>(单轻量模型) | ~~44.4%~~ (未验证) | ~~1,250 ms~~ | ~~1,050 tokens~~ | *Unestimated* | — | — | 待证据补齐 |
| **A1** | Single Capable<br>(单强模型) | ~~88.9%~~ (未验证) | ~~3,150 ms~~ | ~~3,450 tokens~~ | *Unestimated* | — | — | 待证据补齐 |
| **A2** | Dynamic Single<br>(动态单 Agent) | ~~88.9%~~ (未验证) | ~~2,200 ms~~ | ~~2,150 tokens~~ | *Unestimated* | — | — | 待证据补齐 |
| **A3** | Agent Team<br>(多角色协作团队) | ~~88.9%~~ (未验证) | ~~8,850 ms~~ | ~~13,200 tokens~~ | *Unestimated* | — | — | 待证据补齐 |

> **价格合规说明**：根据平台审计规范，对于未公布官方计费单价的模型 API，系统**严格将其费用标记为 *Unestimated*，绝不记为 $0.0 免费**，防止虚构商业成本收益。

---

## 4. 第二人独立复现操作核验单 (Reproduction Checklist)

任何新进入项目的工程师，均可在干净环境仅通过以下 3 步完成 100% 独立复现：

1. **环境准备与依赖安装**：
   ```bash
   git clone https://github.com/hu-qi/moma-devops-agent.git
   cd moma-devops-agent
   pip install -r requirements.txt
   ```
2. **全量离线回归套件自验 (40/40 PASS)**：
   ```bash
   python scripts/run_offline_checks.py
   # 预期结果：Summary: 40 passed, 0 failed (耗时 ~12.5s)
   ```
3. **确定性端到端集成演示复现**：
   ```bash
   devopspilot demo --mode deterministic
   # 预期结果：连续 3 次交付闭环通过，输出格式化交付报告
   ```
