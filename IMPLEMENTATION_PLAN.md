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
**Status**: Not Complete（已扩展为24个fixture案例、6个holdout；fixture验证24/24通过，尚缺、完整 A0–A3 原始 JSONL 和可复算正式报告；当前 A/B 为双方失败后 rejected；执行 R13–R18）

## Stage 5: 比赛材料
**Goal**: 完成 C26–C31，展示、回放、文档及可审核提交包。
**Success Criteria**: 第二人复现；官方要求映射齐全，未核实事项透明。
**Tests**: 离线回放、展示页真实数据、安装和链接检查。
**Status**: Materials Complete / Acceptance Pending（正式材料已生成，见 submission/DevOpsPilot-2026-10-07；第二人独立复现和官网提交尚未完成）

## Web Stage 1: 真实数据与执行契约
**Goal**: 修正 SQLite 状态读取、配置加载、凭据脱敏与严格 Live 入口。
**Success Criteria**: 真实状态可查询；缺少凭据或 API 失败不回退假数据。
**Tests**: canonical SQLite、pending/rejected、脱敏和 Live 失败回归。
**Status**: Complete

## Web Stage 2: 项目工作台与完整交互
**Goal**: 项目/需求/流水线/Agent/轨迹/规则/知识/运行时页面与后台执行。
**Success Criteria**: 查询、筛选、详情、提交、恢复、下载报告均有真实 API；刷新不丢任务。
**Tests**: API 行为、重复启动、任务失败、浏览器交互。
**Status**: Complete

## Web Stage 3: 当前代码验收与交付
**Goal**: 本地测试、真实远端查询和 Web 验收，提供运行指南与证据。
**Success Criteria**: 测试通过；实际 API 和浏览器结果可追溯；未完成 Live 明确记录。
**Tests**: 全量 tests、HTTP smoke、远端只读同步、浏览器截图。
**Status**: Complete
**Evidence**: 全量离线回归 41/41；真实 Issue #7 → PR #8 → 当前提交 CI 成功；MoMA 实际审查/问答与浏览器交互已验收。AgentTeam 超时与原运行发布后补审明确保留，修复后发布前审查的完整 Live 重跑未完成。

## Submission Stage 1: 规则与内容冻结
**Goal**: 官方要求核验、当前代码证据和产品 RoadMap。
**Success Criteria**: 事实与计划分开；未知要求明确列出；全部数字有来源。
**Tests**: 源码 SHA、证据 JSON、规则来源核对。
**Status**: Complete

## Submission Stage 2: 正式文档与答辩材料
**Goal**: 技术方案 DOCX/PDF、答辩 PPTX/PDF、评测报告和复现指南。
**Success Criteria**: 实际文件存在，页面清晰，声明与证据一致。
**Tests**: 全页渲染、文字与链接核对、可编辑性检查。
**Status**: Complete

## Submission Stage 3: 演示视频与可携带证据
**Goal**: 真实页面证据回放 MP4、讲稿、字幕和脱敏归档。
**Success Criteria**: 视频可播放，有旁白字幕，清楚标注回放和未完成边界。
**Tests**: ffprobe、音视频时长、帧抽样和凭据扫描。
**Status**: Complete

## Submission Stage 4: 打包与交付检查
**Goal**: 源码包、提交目录、SHA256 清单、最终 ZIP 和交付报告。
**Success Criteria**: 文件完整、校验通过、无凭据和本地运行垃圾；官网提交待用户确认。
**Tests**: 清单校验、ZIP 解压、源代码回归、敏感信息检查。
**Status**: Complete（材料完整性与敏感值扫描通过；官网上传及队长私密命名待完成）

## Official Submission Stage 1: 更新材料与官方要求
**Goal**: 替换机械配音视频，重新校验统一模板、材料和隐私。
**Success Criteria**: 官方内容完整、字幕视频真实、凭据扫描和ZIP校验通过。
**Tests**: 文件清单、SHA256、递归凭据扫描。
**Status**: Complete

## Official Submission Stage 2: 命名与上传
**Goal**: 按官方队长信息命名并上传初赛作品。
**Success Criteria**: 页面确认文件已上传。
**Tests**: 上传后文件名与页面状态。
**Status**: Complete（用户提供命名信息，内部文件夹与ZIP一致；官网已显示已上传文件）

## Official Submission Stage 3: 正式提交与回执
**Goal**: 用户已授权的最终提交，保存可核验结果。
**Success Criteria**: 官网明确显示提交成功或已提交；否则记录阻断原因。
**Tests**: 页面结果复核。
**Status**: Complete（已点击提交并确认；分片上传完成，重新进入上传页文件仍持久显示。没有审核通过或获奖结论）

## Cloud Stage 1: 资源与报备核验
**Goal**: 确认账号、资源池、ECS/VPC/EIP和部署端口。
**Success Criteria**: 实际控制台和邮件证据一致，已分配与未开通分开。
**Tests**: 北京3资源列表、组委会报备回复、源码运行入口检查。
**Status**: Complete（见docs/deployment/mobile-cloud-readiness.md）

## Cloud Stage 2: 免费资源开通与实例部署
**Goal**: 确认大赛免费开通方式后，部署现有Web/Runtime与持久状态。
**Success Criteria**: 实际实例可运行，凭据与写接口受限，未新增未经报备的公网规则。
**Tests**: Linux安装、服务启动、重启持久化与网络限制。
**Status**: In Progress（免费ECS/VPC已开通，现有EIP已绑定；Linux登录失败，官方密码重置待本人身份验证，尚未安装服务）

## Cloud Stage 3: 云端验收
**Goal**: 真实云端项目/Issue读取、MoMA调用与证据下载。
**Success Criteria**: 实例/公网IP/同版本运行证据可追溯。
**Tests**: 真实API、浏览器、恢复和失败路径。
**Status**: Not Started
