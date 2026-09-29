> **2026-09-29 独立验收结论（当前口径）**：当前作品验收结果为 **不通过**。核心离线实现可在受控环境完成 41/41，但当前 HEAD `6474715` 的 GitHub `Offline Regression and Gates` 失败；默认本机环境会受全局 Git 提交签名影响而失败；Stage 3 真实 Live 尚未接线；DevOpsBench 仅有 9 个合成案例且没有正式 A0–A3 原始结果；正式 PPT、视频和提交包不存在。不得再使用“全部完成”“当前 RC 全绿”“完全满足答辩要求”等表述，直至本文件的 P0/P1 放行项全部完成。
>
> **历史口径**：2026-09-28 的纠偏和质量门禁加固仍保留价值，但其“40/40/全量通过”结论已被当前提交的干净 CI 失败取代。T19、T20、T22、T24 继续保持未完成；此前在比赛 TODO 中把“规划/脚手架/大纲”勾为完成的条目必须按本次整改标准重新验收。

# DevOpsPilot V1 TODO

基线日期：2026-09-26。未勾选表示未完成，文档/代码存在不等于验收通过。每项的证据应包含 commit、命令/运行链接、预期和实际结果。

完成顺序：**基线 → 质量门禁 → 恢复主链 → 行业/评测 → 稳定验收**。P0 是继续扩展前必须修复的正确性问题，P1 是 V1 必需，P2 是延后扩展。

## 2026-09-29 独立验收整改总表

> R01–R29 的逐项修改位置、实现步骤、验证命令、预期结果、证据要求和故障处理见 [独立验收整改执行指南](docs/competition/remediation-execution-guide.md)。本表用于跟踪状态，执行指南用于实际落地；两者的任务编号必须保持一致。

### 执行纪律与证据规则

- [ ] 所有任务只有在“实现、自动化测试、当前 SHA 运行证据、文档口径”四者一致时才能勾选；只有规划、schema、脚手架、大纲或 dry-run 不算完成。
- [ ] 离线模拟、Mock 契约、历史 Live、当前 RC Live 必须分栏记录，禁止相互替代。
- [ ] 每个完成项必须记录：commit SHA、执行命令、退出码、预期/实际结果、CI/远端链接、原始产物路径、降级和人工介入情况。
- [ ] 任一 required workflow 失败、RC 未冻结、Live 未签收、原始评测不可复算或正式交付件缺失时，最终结论必须保持“不通过”。
- [ ] 远端写入、批量 MoMA 调用、比赛报名和材料上传仍需人类明确确认目标、分支、预算与账号；此限制不允许用 dry-run 代替验收。

### Phase A：恢复可信工程基线（P0，必须首先完成）

- [x] **R01 · P0 · 干净安装依赖闭环**（commit `c52f8c3`）：为异步 pytest 用例补充明确测试依赖（优先 `pytest-asyncio`，如采用其他插件必须与现有标记一致），同步更新锁定文件和安装文档。位置：`pyproject.toml`、`requirements-lock.txt`、`docs/setup/environment-and-dependencies.md`。验收：全新 Python 3.11 venv 中仅执行 `pip install -e ".[test]"` 后，`python scripts/run_offline_checks.py` 返回 0；不得依赖开发机已安装插件。证据：空 venv Python 3.11.14，pytest 21 passed，离线 41/41 exit 0（`/tmp/r01_pip_freeze.txt`、`/tmp/r01_offline.log`）。
- [x] **R02 · P0 · 修复当前 HEAD 主 CI**（commit `4db2dde`）：修复 `Offline Regression and Gates` 当前失败，确保 required workflow 对 `src/`、`tests/`、`experiments/`、`benchmarks/`、依赖和脚本修改均触发。位置：`.github/workflows/offline-ci.yml`、`scripts/run_offline_checks.py`。验收：当前候选 SHA 的该工作流为 success，41/41 全部执行且无 skip、xfail 或环境阻塞；失败项必须使 job 非零退出。证据：RC SHA `ddc414a` run https://github.com/hu-qi/moma-devops-agent/actions/runs/36610159951 success；本地 41/41。
- [x] **R03 · P0 · 隔离 Git 全局配置**（commit `ca293f5`）：所有创建临时仓库的 smoke/E2E 必须显式设置本地 `user.name`、`user.email` 和 `commit.gpgSign=false`，不得继承评审机的签名、hooks 或默认分支配置。位置：公共 helper `src/devopspilot/testing/git_isolation.py` + 回归测试 `tests/test_git_isolation.py`，接入 12 处临时仓库初始化点。测试：回归测试证明全局 `commit.gpgSign=true` 且签名不可用时提交仍成功、global config 不被修改；41 项套件全绿。
- [x] **R04 · P0 · 统一 pytest 收集语义**（commit `88b210d`）：明确区分产品测试与故意失败的 benchmark 初始 fixture。修正根目录 `pytest` 会收集红灯 fixture 的问题（`norecursedirs` 排除 `benchmarks/cases/*/fixture`）。位置：`pyproject.toml`。验收：`python -m pytest -q` 62 passed、`python benchmarks/devopsbench/runner.py validate-fixtures` exit 0、`python scripts/run_offline_checks.py` 41/41，三个命令均返回 0；fixture 缺陷仍由 validate-fixtures 证明。
- [x] **R05 · P0 · 消除 CI 假绿**（commit `b2f0394`）：所有 Live/评测脚本必须以任务结果而非“脚本跑完”决定退出码。runtime degraded 默认失败（`ALLOW_RUNTIME_DEGRADED=true` 显式豁免）；gate 拒绝默认失败（`EXPECTED_REJECTION=true` 标记 expected-rejection 专项）；两个 workflow 增加终态校验步骤，解析结构化摘要（`task_success`、`runtime_clean_completion`、`oracle`、`gate`、artifact digest），缺失字段或模式不符使 job 非零。位置：`experiments/openjiuwen-task-executor/main.py`、`experiments/skill-evolution-devopsbench-ab/main.py` 及对应 workflows。证据：本地 41/41、workflow YAML 校验通过；真实 Live 红绿验证待 Phase B 对 RC 执行。
- [x] **R06 · P0 · 发布候选冻结门禁**（tag `rc-2026-mobile-cloud-cup-01` → `ddc414a`）：基于全部 P0 修复后的提交创建唯一 RC tag，回填 Python、OpenJiuwen commit、模型、行业 Pack digest（`fecd034c…`）、case 聚合 digest（`b2c27dbb…`）和 required workflows run URL。位置：`docs/competition/stage3-rc-manifest.md`。验收：工作区干净，tag 指向的 SHA 与所有证据一致，CI run 36610159951 success；任何后续代码变更都必须生成新 RC。

### Phase B：完成当前 RC 的真实交付签收（P0/P1）

- [ ] **R07 · P0 · 接通 Stage 3 `--live`**：实现 `experiments/stage3-live-suite/main.py --live`，不得再返回 `Live mode not yet wired`。必须复用公开 CLI/控制面，不允许为比赛另写绕过产品门禁的专用成功脚本。输入：provider、目标 fixture repo、issue、RC tag、隔离分支前缀、预算和 evidence 输出目录。安全：没有 `DEVOPSPILOT_STAGE3_CONFIRM=YES`、目标不在允许列表、工作区不干净或预算缺失时 fail-closed。
- [ ] **R08 · P1 · S1 正常真实交付**：从当前 RC 完成真实 Issue → 意图 → Plan → 模型路由 → 代码修改 → 独立 Review → 测试 → push → PR → CI → report → trajectory。验收：最终 PR/CI SHA 与报告、Review digest、trajectory 关联一致；无人工直接改代码；记录模型、tokens、耗时、人工介入和 runtime degradation。
- [ ] **R09 · P1 · S2 CI 红转绿真实修复**：准备可重置的隔离 fixture，使第一次 CI 必定失败；控制面读取真实日志、预留预算、完成 RCA、在同一分支推送修复并使 required checks 变绿。验收：至少一个真实红 run 和一个修复后绿 run；attempt 不重置、没有重复 PR、没有人工替 Agent 改代码。
- [ ] **R10 · P1 · S3 行业 Gate 真实拦截与修复**：在同一 RC 上触发一个有明确来源和适用边界的政务审计违规，证明 required gate 阻断发布，再由正式执行链修复并重新通过。验收：保存违规输入、gate finding、修复 diff、复审、测试、CI 与最终验证；文案明确这是工程质量规则示例，不宣称法规认证。
- [ ] **R11 · P1 · S4 中断恢复真实签收**：在 push 后、PR 后或 CI pending 阶段注入真实中断，使用 `resume` 恢复。验收：远端仍只有一个目标分支和一个 PR；预算、attempt、SHA、Review 与 CI 状态不丢失；reconcile 结果进入审计记录。
- [ ] **R12 · P1 · PRD 11 项逐条签收**：将 R08–R11 的同一 RC 原始 JSON 回填 `docs/competition/stage3-prd-signoff.md`，每条必须链接到具体字段或远端证据。验收：11 项不得只引用代码位置或历史 run；至少三轮 Live 和一次恢复全部通过后才能把 T22 勾选。

### Phase C：补齐可复算评测与进化证据（P1）

- [ ] **R13 · P1 · DevOpsBench 扩充至 24 例**：coding、code-review、ci-debug 各 8 例，其中每类至少 2 例固定 holdout。每例包含版本化 `case.json`、合成/公开来源与许可证、初始缺陷、oracle、allowed/forbidden paths、预算、风险和修复前/后确定性验证。位置：`benchmarks/cases/`、schemas、`runner.py validate-fixtures`。验收：24/24 fixture precondition 通过，holdout 默认不参与调优，显式开关才可评估。
- [ ] **R14 · P1 · 冻结 A0–A3 实验契约**：将四组策略统一为同一 RC、case 版本、模型可用性快照、超时、最大调用/重试、上下文和人工介入规则；禁止文档与 runner 对 A0–A3 含义不一致。位置：`docs/demo-guide-and-ablation.md`、`benchmarks/devopsbench/runner.py`、routing comparator。验收：plan 模式输出案例数、变体数、重复数、最大调用量和预算上限，经人工确认后才允许 `--execute`。
- [ ] **R15 · P1 · 运行完整对照实验**：对 24 例 × 4 变体 × 每例至少 3 次执行，保存每次原始 JSONL，不覆盖失败样本。字段至少包含 RC/case/model/variant/repetition、task success、oracle、tokens、耗时、tool/model calls、人工介入、失败分类、runtime health 和价格版本。验收：预期最少 288 条结果；中断可续跑且不会重复计数；所有失败进入分母。
- [ ] **R16 · P1 · 生成可复算评测报告**：从只读原始 JSONL 生成总体、类别、visible/holdout 和重复波动报告；输出成功率、置信区间或分布、P50/P95 耗时、tokens、估算成本、人工介入及失败原因。验收：第二人在全新 clone 中一条命令生成 byte-stable 或数值等价报告；价格未知保持 `unestimated`；禁止把体验额度当作零成本。
- [ ] **R17 · P1 · 受控进化正反两类证据**：保留“负收益/双方失败 → rejected”的真实样例，并新增至少一个 baseline/candidate 均有效且 candidate 有可复算正收益的样例；若没有正收益，如实保持 rejected，不得为了展示强行 PENDING_HUMAN。验收：同一 task/trajectory/candidate id 贯穿，生产 Skill 未被自动修改，正收益最多停在 `PENDING_HUMAN`，真实人工审批和回滚另有审计记录。
- [ ] **R18 · P1 · 原始数据与结果归档**：建立 `docs/evidence/rc-<tag>/benchmarks/` 或等价受版本控制目录，保存 manifest、raw JSONL、汇总、失败样本索引、价格快照与 SHA256SUMS；大文件可使用发布附件，但仓库必须保留不可失效的索引和 digest。完成后才能勾选 T19、T20、T21 的“真实评测”部分。

### Phase D：修复演示、文档与证据可信度（P1）

- [ ] **R19 · P1 · Recorded 模式可携带复现**：`demo --mode recorded` 只能展示已跟踪或随 release 发布的当前 RC 原始产物，不能依赖被 `*.log` 忽略的本机文件，也不能只展示 README/索引。验收：全新 clone 离线运行可看到三轮 Live 的结构化摘要、真实链接、SHA、降级、失败和 artifact digest；缺任何必要证据时返回非零。
- [ ] **R20 · P1 · 文档路径与命令审计**：修正专家指南中不存在的 `src/devopspilot/scm/`、`orchestration/planner.py`、`tests/test_cli_smoke.py` 等路径；统一 40/41、Python 版本、安装命令、CLI 参数、模型名和 RC SHA。验收：自动检查 Markdown 相对链接、反引号内仓库路径和 shell 命令；所有示例在干净环境执行通过。
- [ ] **R21 · P1 · 撤销夸大与矛盾状态**：同步更新 `README.md`、`IMPLEMENTATION_PLAN.md`、`docs/competition/TODO.md`、合规矩阵、专家指南、分镜和 PPT 大纲。删除或降级“全部完成”“100% 覆盖”“完全满足”“当前 RC 全绿”“视频/PPT 已就绪”等无证据表述；规划必须标 `Planned`，dry-run 标 `Simulated`，历史 Live 标 `Historical`，当前 RC 标 `Current RC`。
- [ ] **R22 · P1 · 安全与许可证审计可执行化**：将凭据、Git 历史敏感文件、个人信息 fixture、依赖许可证检查变成有命令、版本和输出的审计流程，不允许仅在 Markdown 中手工写 PASS。验收：扫描器或脚本对当前 SHA 运行，结果和 allowlist 入库；真实密钥模式命中必须阻断；占位符有明确例外；第三方依赖许可证来自锁定版本的实际元数据。
- [ ] **R23 · P1 · 官方规则重新核验**：只使用移动云官方页面、报名系统、官方通知或组委会书面确认，核实赛道、资格、截止时间、评分权重、指定平台要求、原创/开源限制、PPT/视频/压缩包格式和大小。位置：`docs/competition/stage5-competition-compliance-matrix.md`。验收：每条规则有可访问 URL、页面标题、读取日期和原文摘要；未公布项写“待官方确认”，不得标 PASS。

### Phase E：制作真实参赛交付包（P1）

- [ ] **R24 · P1 · 正式技术方案书**：基于当前 RC 和真实评测制作可提交的 PDF/DOCX，至少包含背景、用户、场景、架构、MoMA/OpenJiuwen 分工、可信交付链、行业 Pack、评测方法、真实结果、安全边界、部署复现、商业价值和已知限制。所有数字必须链接到官方来源或原始评测。
- [ ] **R25 · P1 · 正式答辩 PPT**：将 12 页大纲制作成实际 `.pptx` 并导出 `.pdf`；图表只读取 R16 的真实结果，演示链接固定到当前 RC。验收：无字体溢出、无缺图、无未验证数字；逐页讲稿与 8–10 分钟/官方时长匹配；另一台电脑可打开。
- [ ] **R26 · P1 · 正式演示视频**：录制并剪辑实际 MP4，不以 storyboard 代替。必须展示当前 RC 的 deterministic fallback、至少一段真实 Live/recorded 证据、CI 红转绿、行业 gate 和评测结果；所有模拟画面显著标识。验收：时长、分辨率、编码、文件大小满足 R23 官方要求，声音清晰，无 Token、账号、手机号或内部路径泄漏。
- [ ] **R27 · P1 · 现场演示彩排**：在全新目录和备用电脑进行至少两次计时彩排：联网 Live 主路径一次、断网 recorded/deterministic 降级一次。验收：默认 Git 签名开启也能运行；所有命令复制即用；Live 失败能安全停止并在 30 秒内切换降级；保存彩排记录和问题闭环。
- [ ] **R28 · P1 · 最终提交目录与清单**：按官方格式组织源代码/仓库链接、技术方案、PPT/PDF、MP4、复现指南、许可证、评测报告、原始数据索引、团队/报名材料和 checksum。生成 `SUBMISSION_MANIFEST.md`，列出文件名、版本、SHA256、来源、是否公开及上传状态。验收：从空目录按 manifest 校验全部文件，压缩包可解压、无 `.env`/数据库/缓存/临时日志/个人文件。
- [ ] **R29 · P1 · 最终独立验收**：由未参与实现的第二人按官方规则和 reviewer guide 执行。必须同时满足：required CI 全绿、当前 RC tag 固定、三轮 Live + 恢复签收、PRD 11 项有证据、24 例评测可复算、正式材料存在、敏感扫描通过、官方规则矩阵无未知阻断项。输出最终 `PASS/FAIL` 报告；只有 PASS 才允许把作品状态改为“答辩与评审就绪”。

### 建议证据目录结构

```text
docs/evidence/rc-<tag>/
├── manifest.json
├── environment/
│   ├── python.txt
│   ├── dependencies.txt
│   └── required-workflows.json
├── live/
│   ├── s1-normal-delivery.json
│   ├── s2-ci-red-remediation.json
│   ├── s3-industry-gate.json
│   └── s4-interrupt-resume.json
├── benchmarks/
│   ├── sweep-config.json
│   ├── raw-results.jsonl
│   ├── metrics.json
│   ├── report.md
│   └── failures.json
├── security/
│   ├── secret-scan.json
│   └── license-audit.json
└── SHA256SUMS
```

### 最终放行检查表

- [ ] P0 的 R01–R07 全部完成，当前 RC 所有 required workflows 全绿。
- [ ] R08–R12 的三轮真实 Live、一次恢复和 PRD 11 项签收全部完成。
- [ ] R13–R18 的 24 例、holdout、288 条以上原始结果和可复算报告完成。
- [ ] R19–R23 的证据回放、文档、官方规则、安全与许可证审计完成。
- [ ] R24–R28 的方案书、PPT/PDF、视频、彩排与最终压缩包实际存在并验证。
- [ ] R29 第二人独立验收结论为 PASS。
- [ ] 报名、远端发布和上传由人类代表最终确认；自动化不得代替最终法律与参赛承诺。

## 本次评估已完成

- [x] 对照冻结 PRD 梳理 11 项成功标准，记录工作区已有修改。
- [x] 选定 15 个离线 Smoke：14 passed、industry-pack 缺 PyYAML；3 fixture precondition 和 3 指标脚本通过。
- [x] 只读核对同 HEAD 的 E2E success 与后续 fixture checkout failure。
- [x] 复现重复 start 副作用、混合 CI 误判通过、Pack 持久化丢失、DeliveryTask 注解解析错误。
- [x] 修正 README 阶段与研究文档证据边界，形成评估和五阶段实施计划。

## Stage 1：安装、测试与 fixture

- [x] **T01 · P1 · 工程基础**：新增安装元数据、依赖分组与版本锁定；补全 PyYAML 与 Runtime 来源。验收：干净环境一条命令安装，industry import 成功，记录 Runtime 精确版本/commit。位置：根目录 `pyproject.toml`、`requirements*.txt`、[环境配置与依赖文档](docs/setup/environment-and-dependencies.md)。
- [x] **T02 · P1 · CI**：新增统一离线检查入口并接 CI，复用当前 Smoke 和脚本测试，隔离故意失败的 fixture。验收：20 项已纳入离线套件全部通过（15 Smoke + 3 脚本 + 2 fixture）；新改 contracts/industry/atomgit 触发 CI。位置：`scripts/run_offline_checks.py`、[离线 CI 工作流](.github/workflows/offline-ci.yml)。依赖：T01。
- [x] **T03 · P0 · CI**：修复 fixture bootstrap/reset 与 E2E 顺序，限定仓库和命名空间，为共享 fixture 加互斥或按 run 隔离。验收：分支缺失可自愈初始化；并发执行串行互斥；reset 失败阻断 E2E；受控命名空间守卫保护业务分支与 PR。位置：`.github/workflows/*fixture*`、`experiments/github-live-ci-remediation-e2e/main.py`、`experiments/fixture-lifecycle-smoke/main.py`。
- [x] **T04 · P1 · 工程基础**：建立证据索引（SHA、依赖版本、fixture 版本、run id、outcome、人工介入），检查文档内链接。验收：明确区分 Level 1 离线基线、Level 2 Mock 契约、Level 3 历史 Live 运行；文档内所有相对链接校验通过。位置：[证据索引文档](docs/evidence/README.md)。依赖：T02。

## Stage 2：强制质量门禁

- [x] **T05 · P0 · 执行器**：ReviewResult 类型化，绑定 reviewer 身份、被审 diff digest/提交、结论和 findings；独立 reviewer 使用只读权限。验收：REJECT、缺失、超时、旧 diff verdict 均阻断提交/发布；APPROVE 匹配 diff digest 才放行。位置：`src/devopspilot/contracts/review.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/review-gate-smoke/main.py`。
- [x] **T06 · P0 · CI/编排**：required workflows/checks 聚合，校验 HEAD SHA、attempt 与检查身份，处理分页。验收：green+required red 坚决阻断；缺失/运行中保持 pending；旧 SHA 和旧 attempt 过滤。位置：`src/devopspilot/orchestration/ci_aggregator.py`、`src/devopspilot/orchestration/delivery_loop.py`、`experiments/ci-aggregator-smoke/main.py`。
- [x] **T07 · P0 · 执行器**：必要验证命令非空、超时、取消及子进程回收；测试后最终 diff 重新校验与 oracle 防篡改。验收：空命令在要求验证时阻断；超时命令终止并清理进程组；修改 forbidden oracle 测试直接阻断。位置：`src/devopspilot/orchestration/test_runner.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/controlled-verification-smoke/main.py`。依赖：T05。
- [x] **T08 · P0 · Runtime**：移除默认全局 no-op 锁 monkeypatch，固定依赖并完成生命周期最小复现；必要临时适配受版本/开关约束。验收：默认不启用 shim 且不修改全局锁；白名单版本限制与 fail-closed；验证并发写排他性与取消释放。位置：`src/devopspilot/adapters/openjiuwen/lock_shim.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/runtime-lock-lifecycle-smoke/main.py`。
- [x] **T09 · P1 · 验证/轨迹**：区分 task_success、runtime_clean_completion、evidence completeness；统一 verifier。验收：空轨迹与 capture 失败判定为 EVIDENCE_INCOMPLETE 并阻断；degraded 明确记录原因与人工升级路径。位置：`src/devopspilot/orchestration/verifier.py`、`src/devopspilot/contracts/delivery.py`、`experiments/delivery-verifier-smoke/main.py`。依赖：T05–T08。

## Stage 3：持久化主链与 CLI

- [x] **T10 · P0 · 持久化**：start 前记录 delivery intent 与唯一事件键，获取执行 lease；重复请求返回已有任务。验收：重复/并发 start 只有一组执行、发布、PR/评论副作用。位置：`src/devopspilot/contracts/state.py`、`src/devopspilot/persistence/sqlite_state.py`、`src/devopspilot/orchestration/service.py`、`experiments/durable-intent-lease-smoke/main.py`。
- [x] **T11 · P0 · 修复控制面**：remediation 在外部动作前预留 attempt/预算，记录 pending/running/failed/completed；未知结果走 reconcile。验收：executor 抛错、push 后崩溃、CI retry 后崩溃均不重置预算或盲目再次执行。位置：`src/devopspilot/contracts/remediation.py`、`src/devopspilot/persistence/remediation_ledger.py`、`src/devopspilot/orchestration/control_plane.py`、`experiments/remediation-budget-smoke/main.py`。依赖：T10。
- [x] **T12 · P1 · 编排**：按操作阶段保存 checkpoint，并实现远端状态 reconcile。验收：每个副作用前后故障注入，重启恢复到正确 SHA/PR/CI；lease 过期有可审计接管。位置：`src/devopspilot/orchestration/delivery_loop.py`、`src/devopspilot/orchestration/service.py`、`experiments/checkpoint-resume-smoke/main.py`。依赖：T10–T11。
- [x] **T13 · P1 · Planner**：持久化 ExecutionPlan（上下文、路径、风险、模式、模型、预算、测试和审批点）；简单任务单实施 Agent，复杂任务 Team。验收：两分支均可运行、均强制独立 Review，选择理由可见且可覆盖。位置：`src/devopspilot/contracts/planning.py`、`src/devopspilot/routing/execution_planner.py`、`src/devopspilot/adapters/openjiuwen/executor.py`、`experiments/execution-planner-smoke/main.py`。依赖：T05、T10。
- [x] **T14 · P1 · 产品入口**：实现 `start/status/resume/report` CLI 与配置装配，统一 repository binding、任务标识、可信配置与不可信 Issue 内容。验收：用户无需修改 experiment 脚本即可输入 repo/issue 开始任务，错误信息可定位。位置：`src/devopspilot/cli/`、`pyproject.toml`、`experiments/cli-smoke/main.py`。依赖：T12–T13。
- [x] **T15 · P1 · 报告**：将 live 脚本中的报告与验证流程迁入产品服务，报告记录计划、模型、Review、tests、CI、SHA、trajectory、降级和人工介入。验收：E2E 使用同一 CLI/服务，报告内容与持久化证据一致。位置：`src/devopspilot/orchestration/report_service.py`、`src/devopspilot/cli/main.py`、`experiments/delivery-report-smoke/main.py`。依赖：T09、T14。

## Stage 4：行业、评测与进化

- [x] **T16 · P1 · 契约/持久化**：替换未定义 Any 为明确 PackRef/协议；绑定版本与 digest；贯穿 start、state codec、resume、remediation。验收：注解可解析、旧 state 可读、新 state roundtrip 不丢 Pack，修复沿用同一版本，配置失败不再静默忽略。位置：`src/devopspilot/contracts/industry.py`、`src/devopspilot/contracts/delivery.py`、`src/devopspilot/persistence/sqlite_state.py`、`src/devopspilot/orchestration/delivery_loop.py`、`experiments/industry-pack-contract-smoke/main.py`。依赖：T12。
- [x] **T17 · P1 · 行业规则**：选定一个行业任务并核验规则来源/适用边界，区分规范要求与工程建议。验收：每条强制规则有来源和适用条件；没有依据的规则保持建议，不能以示例宣称认证合规。位置：`src/devopspilot/contracts/industry.py`、`src/devopspilot/industry/rules/gov_audit_checker.py`、`src/devopspilot/industry/rules/finance_precision_checker.py`、`industry-packs/`、`experiments/industry-rule-engine-smoke/main.py`。
- [x] **T18 · P1 · Gate runner**：实现受控行业 gate，替换打印 PASS / Decimal 常量示例；结果进入最终 verifier。验收：真实候选违规会失败，修复会通过，再引入缺陷会失败；required gate 超时/缺失也阻断。位置：`src/devopspilot/contracts/industry.py`、`src/devopspilot/industry/gate_runner.py`、`src/devopspilot/orchestration/verifier.py`、`experiments/industry-gate-runner-smoke/main.py`。依赖：T07、T16–T17。
- [ ] **T19 · P1 · Bench**：实现 structured-review evaluator 与有标注 oracle，扩到 coding/review/ci-debug 各至少 3 例，再完成总计 20–30 个 case。验收：正确/错误/漏报/误报可区分；固定版本、许可证/来源、holdout 与允许改动边界。位置：`benchmarks/devopsbench/review_evaluator.py`、`benchmarks/devopsbench/runner.py`、`benchmarks/cases/`（9 个真实案例）、`experiments/structured-review-evaluator-smoke/main.py`。
- [ ] **T20 · P1 · Bench/路由**：用同题同预算执行 A0/A1/A2/A3，对齐 Runtime/模型/案例版本和失败统计；每组每题至少 3 次为初始目标。验收：原始结果可复算，tokens/时间/人工介入/失败原因齐全；价格未知不记为免费；无收益就不推广 Team/候选。位置：`benchmarks/devopsbench/routing_comparator.py`、`experiments/routing-comparator-smoke/main.py`。依赖：T13、T19。
- [x] **T21 · P1 · Evolution**：真实 Report/Trajectory → 一种 Skill/Prompt Candidate → 离线 eval → gate → PENDING_HUMAN；保留版本回滚机制。验收：同 task id 贯穿全链；负增益拒绝；合成 approval 仅用于测试，生产晋级必须真实批准。位置：`src/devopspilot/contracts/evolution.py`、`src/devopspilot/evolution/engine.py`、`src/devopspilot/evolution/miner.py`、`experiments/governed-evolution-smoke/main.py`。依赖：T15、T19；与 T20 共同完成最终对照。

## Stage 5：验收与扩展

- [ ] **T22 · P1 · 集成**：固定发布候选 SHA，在干净环境连续完成 3 次独立真实交付，至少一次 CI 红→自动修复→绿。验收：11 条 V1 要求逐项有同一 run 的证据；fixture 可独立准备和重置。位置：`experiments/end-to-end-integration-suite/main.py`。依赖：T01–T21。
- [x] **T23 · P1 · 集成**：验证权限不足、模型不可用、CI 长时间 pending、中断恢复和预算耗尽。验收：安全停止/人工升级且保留证据，不无限重试，不把 policy failure 自动改成绕过限制。位置：`experiments/failure-boundary-governance-smoke/main.py`。依赖：T22。
- [ ] **T24 · P1 · Demo**：整理真实录屏、操作文档、架构与四组对照表，准备 live/recorded/deterministic fallback。验收：第二人能复现；历史记录有标签；没有虚构收益或隐藏 degraded。位置：`experiments/demo-cli-smoke/main.py`、[演示与消融文档](docs/demo-guide-and-ablation.md)。依赖：T22–T23。
- [x] **T25 · P2 · Provider**：在 GitHub V1 收敛后选择一个国产平台（AtomGit `huqi/DevOpsPilot-Test`），核对官方 API/CLI 契约，跑通真实 Issue→MR/PR，并严格收缩未经证实的 capabilities。验收：脱敏请求/响应和真实 run 链接齐全；平台无原生 Actions Runs 能力显式标记 unsupported 并支持 webhook-only。位置：`src/devopspilot/adapters/atomgit/`、[证据索引文档](docs/evidence/README.md)。

## 暂缓

- 新增工业/医疗完整 Pack；同时补齐六平台全部 API。
- 重型 Web 管理后台、全云部署、自动生产发布。
- 扩展更多 Swarm/Team 进化类型，或在无可比较 Bench 结果时自动晋级。

这些是范围收敛决定，不是删除现有探索。完成 V1 后依据真实使用和评测结果重新排序。
