# 移动云杯作品实施计划

详细任务及证据标准见 docs/competition/TODO.md。阶段完成必须用当前版本证据证明；全部阶段完成后删除本文件，保留详细任务和证据归档。

## Stage 1: 入口与测试基线
**Goal**: 完成 C01–C07，修复正式演示阻断并统一测试入口。
**Success Criteria**: 干净安装成功，live 参数和 API 契约正确，pending 不误报完成。
**Tests**: 40 项离线套件、tests/、CLI demo/provider/状态负向测试。
**Status**: Completed（2026-09-28，C01–C07 全部完成，离线回归 41/41 通过）

## Stage 2: 可信交付主链
**Goal**: 完成 C08–C14，配置与门禁贯通，控制面驱动完整交付。
**Success Criteria**: 同一公共入口修复 CI，恢复不重复副作用，证据关联准确。
**Tests**: 门禁反例、single/team、故障注入、预算与意图恢复测试。
**Status**: Completed（2026-09-29，C08–C14 全部完成，离线回归 41/41 通过）

## Stage 3: 行业 Live 签收
**Goal**: 完成 C15–C19，固定 RC 的三轮真实交付与恢复。
**Success Criteria**: 同 run 对齐 11 条 PRD，真实 CI 红绿与人工介入可追溯。
**Tests**: 三轮真实 E2E 与一次中断恢复，目标/预算未确定前只准备。
**Status**: Prepared（2026-09-29，C15–C19 可离线准备部分全部完成，dry-run 四场景通过，41/41 回归通过；真实 Live 待 RC 冻结+远端写入确认）

## Stage 4: 评测与进化
**Goal**: 完成 C20–C25，20–30 例可复算评测和真实候选。
**Success Criteria**: 原始数据与收益可复算，候选保持人工审批边界。
**Tests**: oracle 正反例、指标重算、负收益拒绝、回滚。
**Status**: Prepared（2026-09-29，C20–C25 可离线准备部分全部完成，41/41 回归通过；真实评测调用待 RC 冻结与预算确认）

## Stage 5: 比赛材料
**Goal**: 完成 C26–C31，展示、回放、文档及可审核提交包。
**Success Criteria**: 第二人复现；官方要求映射齐全，未核实事项透明。
**Tests**: 离线回放、展示页真实数据、安装和链接检查。
**Status**: Completed（2026-09-29，C26–C31 全部完成，包含一键演示脚本、视频分镜、专家指引、答辩 PPT 大纲、许可证与脱敏审计、官方赛道矩阵）
