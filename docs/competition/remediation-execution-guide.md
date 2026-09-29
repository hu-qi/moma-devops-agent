# DevOpsPilot 独立验收整改执行指南

对应根目录 `TODO.md` 的 R01–R29。本文回答“具体怎么做、改哪里、怎么证明完成”；`TODO.md` 保留优先级、依赖和放行状态。

## 0. 通用执行方式

1. 从未完成的最小任务开始，一次只处理一个 R 编号。
2. 修改前记录 `git rev-parse HEAD` 和 `git status --short`；不得清理与该任务无关的本地文件。
3. 先补失败测试或可复现命令，再实现最小修复，最后运行该任务专项测试和全量回归。
4. 每个任务使用独立提交，提交信息写明原因，例如 `fix(ci): install async pytest plugin for clean runs (R01)`。
5. 在 `docs/evidence/rc-<tag>/manifest.json` 或阶段性证据索引中登记命令、退出码、产物 digest 和远端 URL。
6. 只有实际结果满足 `TODO.md` 验收条件后才勾选；计划、代码 review 或一次偶然通过不能勾选。

建议每次任务结束至少执行：

```bash
git diff --check
python -m compileall -q src tests benchmarks/devopsbench
python scripts/run_offline_checks.py
git status --short
```

若当前任务本来就是修复全量回归，允许在修复过程中失败，但提交前必须保存失败前后的完整结果。

## Phase A：可信工程基线

### R01：干净安装依赖闭环

操作步骤：

1. 查看 `tests/` 中的 pytest markers；当前 `tests/test_intent_classification.py` 使用 `@pytest.mark.asyncio`，因此采用 `pytest-asyncio`，不要为绕过失败把异步测试改成同步或删除 marker。
2. 在 `pyproject.toml` 的 `test` 和 `all` extras 中加入 `pytest-asyncio`；先使用兼容范围，安装验证后把解析出的精确版本写入 `requirements-lock.txt`。
3. 在 pytest 配置中明确 `asyncio_mode`；若现有测试均显式标 marker，优先 `strict`，如确需自动识别则说明采用 `auto` 的原因。
4. 更新 `docs/setup/environment-and-dependencies.md`，说明 core、test、runtime 三种安装方式和锁文件用途。
5. 不得依赖本机 `.venv` 验证；必须新建空 venv。

验证命令：

```bash
tmp_dir="$(mktemp -d)"
python3.11 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip install -e ".[test]"
"$tmp_dir/venv/bin/python" -m pytest -q tests/
"$tmp_dir/venv/bin/python" scripts/run_offline_checks.py
```

预期：异步测试实际执行且通过，无 `PytestUnknownMarkWarning`，离线入口返回 0。保存 Python 版本、安装日志、`pip freeze` 和测试摘要。

### R02：修复当前 HEAD 主 CI

操作步骤：

1. 先在 R01 的空 venv 复现 GitHub 错误，确认不是 Actions 特有问题。
2. 检查 `.github/workflows/offline-ci.yml` 是否安装 `.[test]`、是否在正确目录运行、是否使用 Python 3.11。
3. 将 job 名称从历史的“15 Smokes”改成当前真实套件数量或中性名称，避免输出口径漂移。
4. 保留 `--fail-fast` 只用于快速失败；另提供一次不 fail-fast 的诊断运行或确保失败日志能看到具体测试。
5. 推送后只接受当前提交 SHA 对应的 workflow；不能引用旧提交的绿色 run。

验证：本地 41/41；GitHub `Offline Regression and Gates` 为 success；检查 run 的 head SHA、安装步骤和最终摘要一致。将 run URL 写入 RC manifest。

### R03：隔离 Git 全局配置

操作步骤：

1. 搜索所有创建临时仓库的位置：

   ```bash
   rg -n 'git.*init|"init"|git\("commit"|subprocess.*git' experiments tests src
   ```

2. 复用一个简单 fixture helper，在每个临时仓库初始化后设置：
   - `user.name=DevOpsPilot Test`
   - `user.email=devopspilot-test@example.invalid`
   - `commit.gpgSign=false`
   - 必要时 `core.hooksPath` 指向空的临时目录，防止继承用户 hooks。
3. 不要修改用户的 global Git config；所有设置必须使用 `git -C <repo> config --local ...` 或单命令 `git -c ...`。
4. 为 helper 增加回归测试：人为设置 `GIT_CONFIG_COUNT` 或隔离 HOME，使全局 `commit.gpgSign=true` 且签名不可用。

验证：在上述故障环境运行 `git-publisher-smoke`、`controlled-verification-smoke`、`cli-smoke`、E2E、fixture lifecycle 和全量 41 项；全部返回 0。再确认真实工作仓库的 global config 没被改动。

### R04：统一 pytest 收集语义

推荐实现：把 benchmark 初始缺陷测试从普通 pytest 收集范围中排除，继续由 `runner.py validate-fixtures` 执行。

操作步骤：

1. 确认 `benchmarks/cases/**/fixture/test_*.py` 是故意失败的 oracle，不是产品单测。
2. 将 `[tool.pytest.ini_options].testpaths` 收敛到 `tests` 和真正的实验单测目录；不要包含原始 defect fixture。
3. 如部分 `experiments/**/test_*.py` 必须保留，明确列出目录或使用 `norecursedirs` 排除 `benchmarks/cases`。
4. 保留 `runner.py validate-fixtures`，它的成功语义是“初始缺陷按预期存在”。
5. 在 CI 同时运行常规 pytest 和 fixture validator，两个命令都必须是绿色。

验证命令：

```bash
python -m pytest -q
python benchmarks/devopsbench/runner.py validate-fixtures
python scripts/run_offline_checks.py
```

预期：三个命令均返回 0；不得通过修改有缺陷 fixture 让其初始测试变绿。

### R05：消除 CI 假绿

操作步骤：

1. 为 `openjiuwen-task-executor` 定义成功条件：必须打印一条可解析 JSON 终态，且 `task_success=true`、oracle 通过、代码变更存在、Review 通过；运行时降级是否允许必须由 workflow 参数明确控制。
2. 为 Skill A/B 区分两类 workflow：
   - `expected-rejection`：用于证明双方失败或负收益会被拒绝，结果必须是 `gate=false/rejected`；
   - `positive-ablation`：用于证明候选收益，baseline/candidate 都必须是有效运行，candidate 达到门槛且状态为 `PENDING_HUMAN`。
3. 在 Python 主函数末尾按语义返回非零；不要仅打印失败 JSON 后自然退出 0。
4. workflow 在上传 artifact 前运行一个小验证器，检查 schema、终态字段和预期模式；`if: always()` 只用于保留诊断 artifact，不得掩盖主步骤失败。
5. 增加测试覆盖：无最终 marker、timeout、双方 task failure、oracle failure、unexpected gate state 均使验证器失败。

验证：分别运行一次预期拒绝路径、一次故障注入和一次真正成功路径，确认 GitHub job 颜色和业务结果一致。

### R06：冻结 RC

操作步骤：

1. 完成 R01–R05 并合并后，确认 `git status --short` 为空、required workflows 全绿。
2. 计算并记录：

   ```bash
   git rev-parse HEAD
   python --version
   python -m pip freeze
   find benchmarks/cases -name case.json -print0 | sort -z | xargs -0 shasum -a 256
   shasum -a 256 industry-packs/government/pack.yaml
   ```

3. 在 `stage3-rc-manifest.md` 回填真实 SHA、依赖、模型配置、case digest 和 workflow URL。
4. 使用唯一 tag，例如 `rc-2026-mobile-cloud-cup-01`；如果代码变化，创建 `-02`，不得移动旧 tag。
5. 推送 tag 后从远端重新读取 tag SHA，确认没有只存在于本地。

## Phase B：真实交付签收

### R07：接通 Stage 3 Live

操作步骤：

1. 将 `stage3-live-suite` 的场景编排与产品 `devopspilot start/resume/report` 连接，禁止直接构造“成功结果”。
2. CLI 参数至少包括 `--provider`、`--repo`、`--issue-map`、`--target-branch`、`--branch-prefix`、`--rc-tag`、`--evidence-dir` 和 `--budget-limit`。
3. 启动前验证 RC tag、远端仓库 allowlist、fixture 状态、凭据存在、预算非空、证据目录为空。
4. 每个外部副作用前写 intent/lease，执行后立刻记录远端 ID；异常时保留状态供 resume。
5. `--dry-run` 和 `--live` 使用同一场景定义，只替换 provider，不允许两套业务逻辑。
6. 测试未确认、目标不合法、tag 不匹配、预算耗尽和凭据缺失时全部 fail-closed。

验证：先用 fake provider 完成参数/状态测试；再经用户确认对隔离仓库运行一次最小 Live。输出必须符合 `stage3-rc-manifest.md` schema。

### R08：S1 正常交付

1. 在隔离仓库创建一个单文件、oracle 明确、初始 CI 绿色的 Issue。
2. 从 RC tag 启动 `devopspilot start`，保存 delivery id。
3. 等待真实模型、Review、push、PR 和 required checks 完成，不手工改目标分支。
4. 执行 `status` 和 `report`，对照远端 PR HEAD SHA。
5. 导出 state、report、trajectory、Review digest、测试输出和 CI run 元数据到 `live/s1-normal-delivery.json`。

验收重点：任务成功不等于 runtime clean；两个字段都要记录。PR、CI、报告、trajectory 必须指向同一 commit。

### R09：S2 CI 红转绿

1. 使用专用可重置 fixture 分支，reset 后必须由真实 CI 证明为红。
2. 记录首次失败 run ID、HEAD SHA 和日志摘要。
3. 让控制面预留 remediation attempt，再读取该 run 日志并生成 RCA。
4. 修复只能落在同一源分支；重新执行 Review、本地测试并 push。
5. 记录第二次 CI 绿色 run，确认 PR 未重复创建、attempt 为 1、预算未重置。

验收：删除任何一次红/绿 run、无法关联 SHA、人工直接修复代码或重复 PR 都判失败。

### R10：S3 行业 Gate

1. 选择一条 Pack 中 `mandatory` 且有 `authority_source`、`applicability_condition` 的规则。
2. 构造最小违规变更并先运行 gate，保存 finding；确认 verifier 阻断 push/完成状态。
3. 通过正式执行器修复，不允许手工把 gate 配置改成 advisory。
4. 对修复后的同一 diff 重新执行 Review、测试、gate 和 CI。
5. 导出违规前后结果和 pack id/version/digest。

### R11：S4 中断恢复

1. 提供只在 fixture 仓库启用的 fault injection 点，例如 `after_push`、`after_pr_opened`、`while_ci_pending`。
2. 第一次运行在指定点退出，保存 delivery state 和远端状态。
3. 用同一 delivery id 执行 `resume`，不得重新 `start` 新任务。
4. 比较恢复前后分支、PR、attempt、预算和评论数量。
5. 重复一次 resume，证明幂等。

### R12：PRD 11 项签收

对 `stage3-prd-signoff.md` 每一行填写：场景、JSON Pointer/字段、远端 URL、commit SHA、结论。不可填写“见源码”或“smoke 通过”。运行一个校验脚本确认 11 行均不是“待 Live”，所有链接属于当前 RC。

## Phase C：评测与进化

### R13：扩充 24 例

1. 先升级 benchmark schema，增加 `holdout`、`allowed_paths` 和必要 provenance 字段；对现有 9 例完成迁移。
2. 每次新增一个案例：先写 fixture 和 case metadata，运行 precondition，制作已修复临时副本验证 oracle，再加入全量 validator。
3. coding/review/ci-debug 各 8 例；每类固定 2 个 holdout。holdout 题可以公开 fixture，但不得把其结果用于候选生成或 prompt 调优。
4. structured review 例必须分别覆盖 TP、TN、FP、FN，不能只检查一个关键词。
5. 为 case id、版本、目录名唯一性和 schema 增加自动测试。

验证：`validate-fixtures` 报告 total=24、passed=24；默认 sweep 排除 6 个 holdout，显式参数才包含。

### R14：冻结 A0–A3 契约

建立 `sweep-config.json`，记录 RC、case digest、四种 variant 的模型和执行模式、每题重复次数、token/时间/重试预算、温度、Review 和工具集合。runner 必须读取该文件，不能在文档和源码各维护一套定义。执行前输出预计调用数；24×4×3 应为 288 次任务运行。

### R15：执行 288 条以上对照

1. 先运行 plan：

   ```bash
   python benchmarks/devopsbench/runner.py sweep --category all --repeats 3 --variants A0,A1,A2,A3
   ```

2. 人工确认预算后，使用当前 RC 的实际 executor 执行并追加到唯一 JSONL；每条以 `(case_id, variant, repetition, rc_sha)` 为幂等键。
3. 中途失败保留记录；续跑只补缺失键。
4. 每完成一批就校验 JSON schema、行数、重复键、缺失字段和 artifact digest。

注意：当前 `runner.py sweep --execute` 仍需核实是否真正调用模型；如果只产生计划/占位结果，必须先完成执行器接线，不能用占位 JSONL 计数。

### R16：生成报告

1. 扩展 `recompute_metrics.py` 支持 category、holdout、P50/P95、runtime health、失败分类和重复波动。
2. 从 raw JSONL 单向生成 `metrics.json` 和 `report.md`，生成器不能修改 raw 文件。
3. 加入完整性校验：行数不足、失败未进分母、未知价格写 0、重复键或 case digest 不匹配时返回非零。
4. 在第二个空目录复制 raw/config/prices 后重算，对比数值结果。

### R17：进化正反证据

先把现有双方失败案例归档为 negative evidence；不要称为 A/B 收益。再选择 baseline 可稳定通过部分步骤的案例运行 candidate。如果 candidate 没有正收益，正确结果仍是 rejected。只有 baseline 和 candidate 都是有效评测、门禁收益成立时才能生成 `PENDING_HUMAN`，并验证生产 Skill 无变化。

### R18：评测证据归档

把 config、raw JSONL、metrics、报告、失败索引和价格快照放入 RC 目录；运行 `shasum -a 256` 生成 `SHA256SUMS`。若 raw 文件使用 release artifact，仓库索引必须记录 artifact URL、GitHub artifact id、大小和 digest。

## Phase D：演示、文档与审计

### R19：Recorded 模式

1. 定义 recorded manifest，只列出当前 RC 允许展示的 tracked/release artifacts。
2. CLI 按 manifest 校验文件存在和 SHA256，不再 `glob("*")` 展示本机偶然存在的 ignored 日志。
3. 输出每个场景的结果、远端 URL、SHA、模型、降级和人工介入；不把 Markdown 索引当作运行证据。
4. 在全新 clone、断网、没有 `.env` 的环境测试。

### R20：路径与命令审计

新增只读文档检查脚本：解析 Markdown 相对链接及形如 `` `src/...` ``、`` `tests/...` `` 的仓库路径；不存在则失败。对 fenced shell 命令维护可执行 allowlist，在临时目录验证安装、离线测试、demo 和 report 示例。修正专家指南中的旧 `src/devopspilot/scm/` 等路径为真实 adapters 路径。

### R21：统一状态口径

以根 `TODO.md` 为单一完成状态来源。写一个小检查，禁止比赛文档在对应 R 未勾选时出现“完全完成/100%/全部就绪”等绝对词，允许的历史引用必须紧邻 `Historical` 标签。统一 README、计划、比赛 TODO、矩阵、PPT 大纲和分镜中的 41 项、RC 和评测数字。

### R22：安全与许可证审计

1. 选择项目现有工具或新增最小脚本，扫描 tracked files 和 Git 历史；不读取/打印本机 `.env` 内容。
2. 将占位符放入精确 allowlist，真实高熵密钥、私钥头、token 前缀或提交过的 `.env` 必须失败。
3. 对 fixture 的手机号/身份证等只记录文件、规则和“合成数据”依据，不在报告重复敏感值。
4. 从锁定依赖的安装元数据收集 name/version/license/source；unknown 必须人工核查，不能自动写兼容。
5. 输出 JSON 和摘要 Markdown，并保存扫描器版本。

### R23：官方规则

逐项打开移动云官方大赛页、报名页和通知；记录 URL、标题、发布日期/读取日期和规则摘要。对登录后才能查看的要求，由人类代表导出官方文件或截图并登记来源。未找到精确依据的文件大小、时长、评分权重等保持 `待官方确认`，不得引用同名其他赛事或“通常要求”。

## Phase E：真实参赛交付物

### R24：技术方案书

先完成 R12、R16、R22、R23，再写方案书。所有架构和功能来自当前 RC；所有效果数字从 `metrics.json` 自动引用。导出 PDF/DOCX 后检查目录、字体、图片、链接、页码和元数据，不得保留内部路径或作者隐私。

### R25：答辩 PPT

用 `stage5-presentation-outline.md` 作为输入而非最终产物。制作 `.pptx`，图表由 R16 数据生成并标注样本数/RC；每页只保留一个主结论。导出 PDF，逐页检查字体、裁切、对比度、来源和讲稿时长。不存在正式文件时矩阵必须保持“未就绪”。

### R26：演示视频

按官方时长录制 1080p 屏幕和清晰旁白。录制前使用隔离账号/仓库，隐藏通知和 Token。画面角标区分 `LIVE`、`RECORDED CURRENT RC`、`SIMULATED`。剪辑后用媒体信息工具验证编码、时长、分辨率和大小，抽查首尾及关键场景，再进行敏感信息复看。

### R27：现场彩排

准备两份 runbook：联网 Live 和断网 fallback。由第二人在空目录照文档执行，全程计时并记录每次人工输入。主动开启 Git signing、断网或撤销模型凭据验证降级。每个发现转成新的 TODO 或修复提交；两轮都通过才签字。

### R28：提交包

按 R23 官方结构建立临时 staging 目录，不直接压缩工作仓库。只复制 manifest 允许的文件；排除 `.git`、`.env`、`.venv`、SQLite、缓存、ignored 日志和本机截图。生成 SHA256 清单，解压到另一个空目录后重新校验并执行 reviewer guide。

### R29：第二人最终验收

验收人不得参与本轮实现。其输入仅为官方规则、提交包和公开仓库；不得使用开发者本机 `.env` 或 ignored artifacts。逐项核对最终放行表，保存命令、退出码和结论。任一 P0/P1 未完成即输出 FAIL；不得写“基本通过”后仍标记答辩就绪。

## 完成状态更新方式

完成某项后：

1. 在根 `TODO.md` 将对应 R 勾选，并在同一行或紧邻子项写入 commit、命令摘要和证据链接。
2. 更新 `IMPLEMENTATION_PLAN.md` 对应 Stage 状态；只有该 Stage 所有 required R 完成才能写 `Complete`。
3. 更新 RC manifest 和 `SHA256SUMS`。
4. 如果结论影响 README/比赛材料，同一提交同步修正，避免再次出现文档自称完成而证据未完成。

