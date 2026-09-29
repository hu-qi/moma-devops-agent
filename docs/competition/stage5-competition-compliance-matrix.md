# DevOpsPilot 官方赛道规则、交付材料与证据对照表 (C31)

> **文档定位**：移动云杯（中国移动算网人工智能开发者大赛）申报合规核验表与最终提交门禁。  
> **关键发布门禁纪律**：**严禁任何自动化脚本或 Agent 在未经人类参赛代表明确确认的情况下，自动触发赛道报名、上传作品压缩包、调用生产账号扣费或对外发布公开发布。** 本核验表为人类代表提供完整的材料自查清单，所有外部操作均需人类签字放行。

---

## 一、官方赛道定位与参赛资格核验

| 规则项 | 官方赛道要求说明 | 本项目对齐与准备状态 | 核验结论 |
|---|---|---|---|
| **大赛名称** | 2026 中国移动“移动云杯”算网人工智能开发者大赛 | 命名与标识全量对齐（DevOpsPilot 基于移动云 MoMA 平台） | **符合 (PASS)** |
| **赛道定位** | AI 智能体开发 / 大模型行业应用 / 算网智能化开发 | 聚焦端到端自主研发交付控制面，融合 OpenJiuwen 智能体与 MoMA | **符合 (PASS)** |
| **平台技术栈** | 深度结合中国移动大模型能力（MoMA / 九天基座） | 全面适配 MoMA API 网关，集成 Qwen3-32B、DeepSeek-V4.1-Flash、R1 等自营模型 | **符合 (PASS)** |
| **原创性与版权** | 作品须为自主研发原创，无知识产权纠纷，代码开源合规 | 拥有独立的架构设计、全套测试代码与基准题库；协议采用 Apache-2.0，无侵权组件 | **符合 (PASS)** |
| **可复现性要求** | 评审专家可在规定环境完整复现作品功能 | 提供零外部网络与凭据依赖的一键本地复现（`./scripts/run_demo.sh deterministic`） | **符合 (PASS)** |

---

## 二、官方交付材料与证据路径逐项对照表 (Rules to Materials Matrix)

| # | 官方申报材料要求 | 本项目对应材料文档 / 代码产物 | 核心内容与证据支撑 | 状态 |
|---|---|---|---|---|
| **1** | **项目源代码包** | `src/devopspilot/`<br>`tests/`<br>`benchmarks/` | 完整控制面、适配器、门禁、持久化存储与 CLI 实现；全量 41 项离线测试全绿 | **就绪** |
| **2** | **技术方案说明书** | `docs/competition/stage5-presentation-outline.md`<br>`README.md` | 行业痛点、架构全景、MoMA 平台价值（降本 30%）、Single Agent First 理念 | **就绪** |
| **3** | **答辩演示文稿 (PPT)** | `docs/competition/stage5-presentation-outline.md` (§二) | 12 页幻灯片完整结构、图表设计、讲稿要点与数据来源 | **就绪** |
| **4** | **演示视频与分镜脚本** | `docs/competition/stage5-video-storyboard.md` | 3 分 30 秒标准分镜：特性交付、CI 红灯 RCA、断点 resume、合规拦截、DevOpsBench | **就绪** |
| **5** | **专家快速复现指南** | `docs/competition/stage5-reviewer-guide.md` | 3 分钟一键复现路径、PRD 11 条成功指标核验表、工程已知边界说明 | **就绪** |
| **6** | **消融评测与对照报告** | `docs/demo-guide-and-ablation.md`<br>`benchmarks/devopsbench/` | A0–A3 同题同预算基准；MoMA 官方自营模型资费（91592号文档）；`recompute_metrics.py` | **就绪** |
| **7** | **开源许可证与合规自查** | `LICENSE` (Apache-2.0)<br>`docs/competition/stage5-clean-reproduction-and-audit.md` | 根目录许可证、依赖兼容性矩阵、敏感凭据脱敏扫描报告（无泄漏） | **就绪** |
| **8** | **确定性演示脚本** | `scripts/run_demo.sh` | 一键运行 deterministic / recorded / live 三条路径 | **就绪** |

---

## 三、最终提交放行门禁 (Human Gate for Submission)

依据项目安全纪律，以下外部写操作必须由**项目负责人/人类操作者**在浏览器或本地终端手动完成，严禁 Agent 自动执行：

- [ ] **门禁 1：官方大赛系统注册与团队信息核准**
  - 确认团队成员姓名、手机号、归属单位、指导老师（如有）与比赛官网登记一致。
- [ ] **门禁 2：演示视频终剪与录音**
  - 按照 `stage5-video-storyboard.md` 录制 3~5 分钟高清无水印 MP4，大小符合大赛上传限制（通常 < 200MB）。
- [ ] **门禁 3：PPT 导出为 PDF/PPTX**
  - 根据 `stage5-presentation-outline.md` 大纲美化排版，输出正式答辩幻灯片。
- [ ] **门禁 4：GitHub 仓库公开与 AtomGit 镜像同步**
  - 确认仓库代码提交干净（当前 SHA 已打 tag），在用户网络正常时完成 `git push` 与 AtomGit 镜像同步。
- [ ] **门禁 5：大赛官网材料上传与最终提交确认**
  - 人工点击官网“确认提交”，完成报名与作品报送。
