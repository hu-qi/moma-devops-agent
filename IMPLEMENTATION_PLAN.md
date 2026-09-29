# 移动云杯作品实施计划

详细整改任务及证据标准见根目录 `TODO.md` 的“2026-09-29 独立验收整改总表”，逐项操作方法见 `docs/competition/remediation-execution-guide.md`；比赛执行边界见 `docs/competition/TODO.md`。阶段完成必须用当前 RC 的实现、测试、运行证据和文档一致性共同证明；全部阶段完成后删除本文件，保留详细任务和证据归档。

## Stage 1: 入口与测试基线
**Goal**: 完成 C01–C07，修复正式演示阻断并统一测试入口。
**Success Criteria**: 干净安装成功，live 参数和 API 契约正确，pending 不误报完成。
**Tests**: 40 项离线套件、tests/、CLI demo/provider/状态负向测试。
**Status**: Reopened（2026-09-29 独立验收：当前 HEAD 干净 CI 因缺少异步 pytest 插件失败；默认环境还会继承 Git 提交签名。完成 R01–R04 后重新签收）

## Stage 2: 可信交付主链
**Goal**: 完成 C08–C14，配置与门禁贯通，控制面驱动完整交付。
**Success Criteria**: 同一公共入口修复 CI，恢复不重复副作用，证据关联准确。
**Tests**: 门禁反例、single/team、故障注入、预算与意图恢复测试。
**Status**: Conditionally Complete（离线门禁与故障注入在受控环境通过；完成 R05 假绿治理并由当前 RC required workflows 复验后转为 Complete）

## Stage 3: 行业 Live 签收
**Goal**: 完成 C15–C19，固定 RC 的三轮真实交付与恢复。
**Success Criteria**: 同 run 对齐 11 条 PRD，真实 CI 红绿与人工介入可追溯。
**Tests**: 三轮真实 E2E 与一次中断恢复，目标/预算未确定前只准备。
**Status**: Not Complete（dry-run 可用，但 `stage3-live-suite --live` 尚未接线，RC 未冻结，PRD 11 项均待 Live；执行 R06–R12）

## Stage 4: 评测与进化
**Goal**: 完成 C20–C25，20–30 例可复算评测和真实候选。
**Success Criteria**: 原始数据与收益可复算，候选保持人工审批边界。
**Tests**: oracle 正反例、指标重算、负收益拒绝、回滚。
**Status**: Not Complete（仅 9 个合成案例，无 holdout、完整 A0–A3 原始 JSONL 和可复算正式报告；当前 A/B 为双方失败后 rejected；执行 R13–R18）

## Stage 5: 比赛材料
**Goal**: 完成 C26–C31，展示、回放、文档及可审核提交包。
**Success Criteria**: 第二人复现；官方要求映射齐全，未核实事项透明。
**Tests**: 离线回放、展示页真实数据、安装和链接检查。
**Status**: Not Complete（现有产物主要是脚本、大纲与分镜；正式 PPT/PDF、视频、技术方案书、完整提交包和已核实官方规则尚缺；执行 R19–R29）
