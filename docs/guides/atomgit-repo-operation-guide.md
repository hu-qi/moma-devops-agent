# DevOpsPilot 针对 AtomGit 仓库的全流程详细实操指南

本指南以真实目标仓库 **`https://atomgit.com/huqi/DevOpsPilot-Test`** 为例，提供从环境配置、需求发起、自主交付、状态跟踪到 MR 验收的完整手把手操作手册。

---

## 目录
1. [目标仓库与前置凭据](#1-目标仓库与前置凭据)
2. [环境配置（推荐使用 .env）](#2-环境配置推荐使用-env)
3. [在 AtomGit 仓库中发起 Issue 需求](#3-在-atomgit-仓库中发起-issue-需求)
4. [启动 DevOpsPilot 执行自主交付](#4-启动-devopspilot-执行自主交付)
5. [查看任务实时进度与状态 (Status)](#5-查看任务实时进度与状态-status)
6. [在 AtomGit 网页端验收合并请求 (MR)](#6-在-atomgit-网页端验收合并请求-mr)
7. [导出合规审计与交付报告 (Report)](#7-导出合规审计与交付报告-report)
8. [异常排查与常见问题](#8-异常排查与常见问题)

---

## 1. 目标仓库与前置凭据

- **平台类型**：AtomGit（国产代码托管平台，OpenAPI 端点 `https://api.atomgit.com`）
- **目标仓库主页**：[https://atomgit.com/huqi/DevOpsPilot-Test](https://atomgit.com/huqi/DevOpsPilot-Test)
- **组织/所有者**：`huqi`
- **仓库名称**：`DevOpsPilot-Test`
- **默认主分支**：`main`
- **个人访问令牌 (Token)**：确保具备 `repo`、`issues`、`pull_requests` 权限的 AtomGit Access Token（例如 `PT43FrQdtUb3E3M9r3Jx-xCa`）。

---

## 2. 环境配置（推荐使用 .env）

系统内置了零依赖 `.env` 自动加载机制。在项目根目录下完成配置：

```bash
# 1. 切换到项目根目录并激活虚拟环境
cd /Users/huqi/Develop/todo/test/moma-devops-agent
source .venv/bin/activate

# 2. 如果根目录尚未创建 .env，从模板复制一份
cp .env.example .env

# 3. 编辑 .env 文件，填入 AtomGit 访问凭据
# 在 .env 中确保包含以下行：
ATOMGIT_TOKEN="PT43FrQdtUb3E3M9r3Jx-xCa"
```

> **提示**：配置写入 `.env` 后，每次运行 CLI 会自动生效，无需在 Shell 中重复运行 `export ATOMGIT_TOKEN=...`。

---

## 3. 在 AtomGit 仓库中发起 Issue 需求

DevOpsPilot 以需求（Issue）为生命周期起点。您可以通过以下两种方式之一创建需求：

### 方式 A：AtomGit 网页端创建（直观易用）
1. 打开浏览器访问：[https://atomgit.com/huqi/DevOpsPilot-Test/issues](https://atomgit.com/huqi/DevOpsPilot-Test/issues)
2. 点击页面右上角 **“新建 Issue”**。
3. 输入示例：
   - **标题**：`feat: add email format validation function`
   - **内容/描述**：`在 utils.py 中添加 validate_email 函数，校验邮箱合法性并提供配套单元测试。`
4. 点击 **“确定创建”**。
5. 记录下生成的 Issue 编号，例如 `#1` 或 `#2`。

### 方式 B：终端 API 一键创建
```bash
curl -s -X POST "https://api.atomgit.com/repos/huqi/DevOpsPilot-Test/issues" \
  -H "Authorization: Bearer PT43FrQdtUb3E3M9r3Jx-xCa" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "feat: add email format validation function",
    "body": "Add validate_email function and unit tests."
  }'
```

---

## 4. 启动 DevOpsPilot 执行自主交付

获取到 Issue 编号（假设为 `#1`）后，在终端执行 `start` 命令：

```bash
devopspilot start --provider atomgit --repo huqi/DevOpsPilot-Test --issue 1
```

> **智能 URL 支持**：您也可以直接输入网页完整链接，系统自动识别平台：
> ```bash
> devopspilot start --repo https://atomgit.com/huqi/DevOpsPilot-Test --issue 1
> ```

### 控制台标准输出示例：
```text
Delivery initialized: id=deliv-780c1a18 provider=atomgit repo=huqi/DevOpsPilot-Test issue=1 mode=single_agent
[1/5] Work item resolved: #1 - 'feat: add email format validation function'
[2/5] Execution planning: mode=single_agent (Single Agent First), routing to DeepSeek-V3
[3/5] Coding complete: branch=feat/issue-1-1a18 commit=cbe3c95f
      Independent Review Verdict: APPROVED (No defect findings, review gate passed)
[4/5] Change request opened on atomgit: https://atomgit.com/huqi/DevOpsPilot-Test/merge_requests/1
[5/5] CI Run: SUCCESS | Verifier: ACCEPTED -> VERIFIED_CLEAN

Delivery completed successfully: id=deliv-780c1a18 phase=VERIFIED
To query status:  devopspilot status --delivery-id deliv-780c1a18
To export report: devopspilot report --delivery-id deliv-780c1a18 --format markdown
```

---

## 5. 查看任务实时进度与状态 (Status)

交付完成后或执行过程中，使用系统分配的 `delivery-id` 查询执行状态：

```bash
# 文本格式查看
devopspilot status --delivery-id deliv-780c1a18

# 或 JSON 格式查看（便于机器解析）
devopspilot status --delivery-id deliv-780c1a18 --format json
```

### 状态输出示例：
```text
Delivery ID:   deliv-780c1a18
State Version: 1
Phase:         verified
Commit:        cbe3c95f
Change PR:     mr-1
CI Status:     success
Verified:      True (All acceptance criteria met cleanly and verified against CI.)
```

---

## 6. 在 AtomGit 网页端验收合并请求 (MR)

DevOpsPilot 完成交付后，已在远端 AtomGit 仓库自动发起了合并请求（Merge Request）：

1. 打开浏览器访问：[https://atomgit.com/huqi/DevOpsPilot-Test/merge_requests](https://atomgit.com/huqi/DevOpsPilot-Test/merge_requests)
2. 找到由 DevOpsPilot 自动创建的 MR（例如 `!1 feat: add email format validation function`）。
3. 检查页面详情：
   - **源分支**：`feat/issue-1-1a18` ➔ **目标分支**：`main`
   - **提交记录**：包含对应的 Commit 记录与代码变更。
   - **关联需求**：已关联至对应的 Issue #1。
4. 审查无误后，点击 **“合并”（Merge）**，完成最终生产集成。

---

## 7. 导出合规审计与交付报告 (Report)

在任务验收后，可以随时导出规范的 Markdown 交付报告用于团队归档与审计：

```bash
devopspilot report --delivery-id deliv-780c1a18 --format markdown
```

### 报告核心内容：
* **基本信息**：交付 ID、版本号、所属仓库及源 Issue。
* **规划策略**：调度模式（`single_agent`）、路由模型与成本控制依据。
* **审查证明**：独立 Reviewer 身份标识、Verdict 结论与 Diff Digest 哈希。
* **验收闭环**：远端 Commit SHA、MR 链接及 CI 绿灯凭据。

---

## 8. 异常排查与常见问题

1. **报错 `unable to open database file`**：
   - 解决方案：已在新版中内建父目录自愈创建；确认当前工作区对 `.devopspilot/` 目录具备读写权限。
2. **报错 `Authentication failed` / Token 无效**：
   - 检查 `.env` 文件中的 `ATOMGIT_TOKEN` 是否已过期或带有额外空格。
3. **任务中断后恢复**：
   - 执行 `devopspilot resume --delivery-id <delivery-id>`，系统将自动校验远端状态并从中断检查点继续。
