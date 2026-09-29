# DevOpsPilot

> **MoMA 驱动的自进化多智能体研发交付系统 (Autonomous DevOps Agent)**

DevOpsPilot 是面向政务、金融、工业等高确定性与高合规要求行业的软件研发智能底座。它以移动云 MoMA 作为 MaaS 与多模型调度底座，融合动态 AgentTeam、行业工程合规包（Industry Engineering Packs）、真实离线评测集（DevOpsBench）与受控自进化闭环（Self-Evolving / RSI），实现从需求识别、代码实现、测试审查、CI/CD 修复到知识资产沉淀的自主研发交付。

---

## 📐 核心公式与产品闭环

### 产品公式
```text
DevOpsPilot
= MoMA Model Intelligence
+ OpenJiuwen Agent Runtime
+ Dynamic DevOps AgentTeam
+ Industry Engineering Packs
+ DevOps Skills & Tools
+ DevOpsBench
+ Self-Evolving / RSI
```

### 核心交付闭环
```text
Understand → Plan → Develop → Review → Verify → Deliver → Observe → Evolve
  (需求理解)   (意图分流)  (编码实现)  (独立评审)  (质量门禁)  (平台发布)  (轨迹采集)  (受控进化)
```

---

## 🌟 核心特性与架构亮点

### 1. 🎯 智能意图分流与只读问答通道 (Intent Routing)
- **精准识别**：基于中文口语化词库与轻量仲裁器，自动区分**信息咨询（`INQUIRY`）**与**代码改动（`CODE_CHANGE`）**。
- **只读闭环**：当 Issue 属于列举文件、技术咨询、架构答疑时，系统直接在 Issue 下回复结构化清晰解答并幂等去重，**坚决不拉取无意义分支、不写脏代码、不发起冗余 Pull Request**。
- **Fail-Closed 保护**：输入模糊或意图未知时置为 `NEEDS_CLARIFICATION` 并暂停等待人工确认，支持通过 CLI 参数 `--intent [inquiry|code_change]` 显式覆盖。

### 2. 🛡️ 模型输出三层净化防护 (Sanitization Shield)
- **剔除推理痕迹**：全面剥离模型输出中混杂的 `<think>...</think>` 深度思考标签，保持 Issue 回复和 PR 正文干净整洁。
- **源码自动解包**：当代码生成模型误返回 `{"files": [...]}` raw JSON 或携带首尾 markdown 块（````python ... ````）时，落盘引擎自动解包并提取纯净源码，杜绝将 JSON 字符串写入源码库。
- **路径越界防御**：严格校验模型生成的文件相对路径，拦截绝对路径、`../` 逃逸与禁止文件篡改。

### 3. 🔒 强制质量门禁与凭据隔离 (Fail-Closed Gates)
- **类型化 Review Gate**：Review 结论绑定独立审查者身份、审查时间与 Commit 树的 SHA256 Diff Digest，`REJECT`、超时或空 Review 严格阻断交付。
- **统一 Verifier**：强制校验本地测试结果、CI SHA 一致性与发布状态，拒绝依赖大模型自报“已通过”元数据。
- **环境驱动 Branding & 凭据脱敏**：品牌展示与平台链接完全通过环境变量驱动，未配置时纯文本降级；Git Clone 采用内存级 `http.extraHeader` 注入 Token，异常日志全面脱敏。

### 4. 🏢 行业合规包与规则引擎 (Industry Packs)
- **政务合规（Gov Compliance Pack）**：内建审计日志合规性检查（如敏感数据操作必须带有 traceId 和审计埋点）。
- **金融计算（Finance Precision Pack）**：严格拦截高精度金额计算中使用浮点数运算，强制重构为 `Decimal`。

### 5. 🔄 受控自进化机制 (Governed Evolution)
- **轨迹挖掘**：从交付成功的任务轨迹中自动提炼更优的 Skill 或 Prompt 候选版本。
- **人工审批闭环**：候选版本必须经由 DevOpsBench 离线评测且收益为正，默认状态严格停留在 `PENDING_HUMAN`，严禁无人工确认直接晋级生产，支持快速版本回滚。

---

## 🚀 快速开始

### 1. 环境准备
推荐使用 Python 3.11+：
```bash
# 克隆仓库
git clone https://atomgit.com/huqi/moma-devops-agent.git
cd moma-devops-agent

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装（含测试依赖）
pip install -e ".[test]"
```

### 2. 配置环境变量
复制配置模板并填入对应平台的 Token：
```bash
cp .env.example .env
```
主要配置项说明：
```dotenv
# 代码托管平台凭据（按需配置）
ATOMGIT_TOKEN="your_atomgit_token"
GITHUB_TOKEN="your_github_token"

# 移动云 MoMA / 大模型 API 凭据
MOMA_API_KEY="sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
MOMA_BASE_URL="https://zhenze-huhehaote.cmecloud.cn/v1"

# 品牌展示链接（可选，不配则降级为纯文本）
DEVOPSPILOT_URL="https://atomgit.com/huqi/moma-devops-agent"
MOMA_URL="https://ecloud.10086.cn/portal/product/MaaS"
```

---

## 💻 CLI 使用指南

DevOpsPilot 提供简洁、统一的命令行工具：

### 1. 启动交付任务 (`start`)
自动识别 Issue 意图并执行对应流程：
```bash
# 针对 AtomGit 平台的 Issue 启动任务
devopspilot start --provider atomgit --repo huqi/DevOpsPilot-Test --issue 2

# 显式指定意图类型（inquiry: 直接问答 / code_change: 完整编码并提 PR）
devopspilot start --provider atomgit --repo huqi/DevOpsPilot-Test --issue 2 --intent inquiry
```

### 2. 查看交付状态 (`status`)
```bash
devopspilot status --delivery-id <delivery-id>
```
状态标签与退出码语义（C07）：
- `ACCEPTED (not started)` / `IN_PROGRESS / WAITING`：任务已受理或等待 CI/审查，**不会**打印 completed；
- `FAILED`：CI 失败或验证拒绝；
- `COMPLETED (verified)` / `COMPLETED (answered)`：验证通过（verified 阶段但验证未通过时不显示 completed）。
- 退出码：`0` 成功（含正常查询）；`1` 用法/未找到/凭据或 API 失败等错误。

### 3. 导出交付报告 (`report`)
支持生成包含上下文、计划、审查结论与验证记录的完整 Markdown 报告：
```bash
devopspilot report --delivery-id <delivery-id> --format markdown
```

### 4. 运行演示工作流 (`demo`)
系统提供三种开箱即用的验证模式：
```bash
# 模式 1：确定性离线演示（无需真实 Token，离线跑通三轮交付闭环）
devopspilot demo --mode deterministic

# 模式 2：查看已记录的历史真实证据轨迹
devopspilot demo --mode recorded

# 模式 3：使用 .env 中的真实凭据执行真实端到端交付
devopspilot demo --mode live
```

---

## 🧪 验证与质量保证

DevOpsPilot 严格遵守“证据可复验、拒绝伪造通过”的工程准则。

### 1. 全量离线回归套件 (40 Checks)
```bash
python3 scripts/run_offline_checks.py
```
> **当前状态**：**40 passed, 0 failed**（覆盖 35 项核心 Smoke 测试、3 项度量脚本与 2 项 Fixture 生命周期校验）。

### 2. 连续 3 次独立全流程交付验证
```bash
python3 experiments/end-to-end-integration-suite/main.py
```
- **Run 1（标准特性交付）**：需求分析 → 独立编码 → 独立 Review → 提交并创建 PR。
- **Run 2（CI 自主修复交付）**：模拟 CI 失败 → 触发控制面预留预算 → 针对日志自主修复 → 再次审查并通过。
- **Run 3（行业合规治理交付）**：加载政务/金融规则包 → 违规静态分析拦截阻断 → 自动按规范修复 → 质量门禁全绿放行。

### 3. 单元与专项测试
```bash
python3 -m pytest tests/
```

---

## 📚 延伸文档

- [产品需求文档 (PRD v0.1)](./PRD/01-product-definition.md)
- [证据索引与可信证据文档](./docs/evidence/README.md)
- [演示运行与消融实验指南](./docs/demo-guide-and-ablation.md)
- [开发环境与依赖配置说明](./docs/setup/environment-and-dependencies.md)
- [任务跟踪与验收记录清单](./TODO.md)

---

## 📄 开源许可证

本项目遵循 Apache 2.0 开源许可证。
