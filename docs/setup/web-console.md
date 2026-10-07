# DevOpsPilot Web 工作台

## 启动

在仓库根目录执行：

```bash
uv pip install --python .venv/bin/python -r requirements-lock.txt -r requirements-runtime.txt
.venv/bin/python scripts/serve_dashboard.py --port 8080
```

浏览器打开 `http://127.0.0.1:8080`。也可运行 `devopspilot serve`。
启动时自动读取本地 `.env`，已有进程环境变量优先。`--db` 优先于
`DEVOPSPILOT_DB_PATH`，未配置时采用 `.devopspilot/state.db`。默认只监听本机。
此版本是可信本机操作员控制台，尚未实现多用户登录、RBAC 和公网部署。

## 使用路径

1. **项目场景**：从配置中发现 GitHub/AtomGit 项目，或接入 `owner/repository`。
   点击“交付配置”，填写独立测试命令、允许/禁止修改路径及 required checks。
   这些值属于操作员配置，不能由 Issue 正文覆盖。项目设置保存在 console 数据库。
2. **需求中心**：选择项目并点击“同步远端 Issue”。GitHub 同步最多 100 条 Issue
   和最近 15 条 CI；AtomGit 同步真实 Issue，不伪造平台不存在的 Actions。
   同步时间和数据来源明确展示。同步失败返回实际错误，保留之前的缓存。
3. **启动交付**：填写真实 Issue 编号、模式和意图。自动识别歧义会暂停；
   `code_change` 走编码/Review/分支/PR；`inquiry` 走模型分析和 Issue 回复。
   SCM/MoMA 缺少配置或真实 Issue 获取失败时停止，不回退占位任务。
4. **流水线**：后台提交立即返回任务编号。五秒刷新持久化状态，可按标题、仓库、
   Issue、负责人筛选。点击任务查看 SHA、分支、PR、CI、测试、Review 和轨迹。
   点击阶段或侧栏 Agent 查看配置模型与实际执行证据。
5. **恢复 / 检查 CI**：只对已存在任务调用公共恢复入口；不会把新任务作为恢复。
   同一项目/Issue 的运行任务会去重；已有记录须通过恢复继续，不重复创建任务。
6. **下载交付证据**：导出当前任务 JSON，包括最终验收、Review/CI 链接、
   关联轨迹和后台执行信息。页面和 JSON 均进行凭据脱敏。
7. **定时任务**：创建一次未来的真实交付启动，服务运行时调度；可在执行前取消。
   重启后保留任务，已分发任务不重放；运行进程重启留下的任务标为 interrupted。
8. **Chat Agent**：显式发送问题才调用真实 MoMA；附带选定项目的持久化交付摘要，
   展示实际模型与 usage。这里不调用工具、不修改仓库、不发送 SCM 评论。

## 各页面的数据源

| 页面 | 实际来源 |
|---|---|
| 概览 | 当前 Git SHA/tag、SQLite、真实题库文件、远端同步的 CI |
| 项目 / 需求 | `.env` 中的仓库引用、操作员接入、SCM REST 响应缓存 |
| 流水线 | `SQLiteDeliveryStateStore` 的 canonical `delivery_state.payload` |
| Agent | 当前任务的执行 metadata、Review、轨迹；配置模型单独标明 |
| 场景 · 技能 | `industry-packs/*/pack.yaml` 中实际规则 |
| 知识库 | `PRD/`、`docs/research/`、`docs/setup/` 的 Markdown 文件 |
| DevOpsBench | `benchmarks/cases/*/case.json`，不把题库数量作为评测成绩 |
| 审计轨迹 | 数据库旁 `trajectories/*.json`，按执行 metadata 的 ID 关联 |
| 运行时 | 依赖安装检查、配置是否存在、后台作业与日志 |
| IM 渠道 | 现有 SCM 反馈能力；未配置的 IM 明确显示未接入 |

“VOD / Issue / Coding / QA / SRE”是产品交付阶段视图，不承诺五个独立
常驻 Agent。实际执行模式遵循现有 Single Agent First 与独立 Review 门禁。
QA 不会因编码结束自动变绿；SRE 完成需要持久化验收接受、运行时干净完成
和证据完整。旧记录缺少这些字段时不能证明干净成功。

## 持久化与边界

- 执行状态保持原有 schema，不新增演示行。
- Web 项目、作业、预约和问答位于同目录 `<db-stem>.console.db`。
- 数据库、配置凭据和虚拟环境不进入 Git。
- 进程退出码 0 表示执行结束，不等于最终交付验收通过。
- 任意 job 错误及服务重启中断均保留，页面展示阻断和日志。
- CNB 配置可以展示，但现有 Live 自动装配仅支持 GitHub/AtomGit。
- 未提供 IM 平台配置，因此页面没有虚构 IM 消息发送功能。
- 定时器为本机服务内的一次性调度，不是云端 cron；服务离线时不会执行。
- API 禁止浏览器跨 Origin 写入，拒绝非 JSON 对象和超过 64KB 的请求。
- 当前版本没有自动合并 PR 或自动生产发布入口。

## 验证

```bash
PYTHONPATH=src DEVOPSPILOT_NO_DOTENV=1 .venv/bin/python scripts/run_offline_checks.py --fail-fast
.venv/bin/python scripts/verify_web_live.py
```

`verify_web_live.py` 只读远端项目；添加 `--chat-check` 会产生一次真实 MoMA
问答调用。它不会创建 Issue/PR/评论。证据输出默认保存在
`docs/evidence/web-console-live.json`。

用户授权的受控 Live 验收 Issue 创建工具为
`scripts/prepare_web_acceptance_issue.py`。其目标是配置的 GitHub 仓库，
只有两份 fixture 文件可修改，结果 PR 保持未合并。
该工具会真正创建 Issue，不能作为默认安装步骤或离线自测运行。
