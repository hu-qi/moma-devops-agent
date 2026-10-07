# CodeArts · DevOpsPilot 参赛交付包

2026-10-07制作；2026模型应用赛。正式答辩沿用用户提供的附件2模板，覆盖官网要求的五个内容领域。

## 阅读顺序
1. DevOpsPilot-参赛答辩.pptx / PDF：12页可编辑答辩。
2. DevOpsPilot-技术方案书.docx / PDF：8页完整技术方案。
3. DevOpsPilot-演示视频.mp4：约189秒真实截图与证据回放，合成中文旁白、内嵌字幕；并非连续Live录屏。
4. EVALUATION_REPORT.md、ROADMAP.md：实际证据、缺口、后续里程碑。
5. EVIDENCE_REPLAY.html：直接浏览器打开；不需要密钥或网络即可查看已归档证据。
6. REPRODUCTION_GUIDE.md：运行源码与重新验收的条件。
7. APPLICATION_TEXT.md、OFFICIAL_RULES.md、LICENSE_AND_ORIGINALITY.md：申报文本、规则映射与依赖说明。

## 核验边界
真实Issue #7 → PR #8 → 对应提交CI成功；PR未合并。运行标记verified_degraded，AgentTeam曾超时，原交付补审发生在发布后。修复后发布前审查的完整Live重跑尚未完成。41项离线检查与24例fixture验证不代表行业任务成功率。没有宣称未经实测的降本、客户或收入。

源码ZIP基于7076541e445a9f2da365b52fce74cf6df3c4ff17。打包时移除了历史AtomGit指南中的凭据值，运行代码未改动。源仓库历史指南仍需维护者轮换凭据并清理历史。其余历史比赛文档仅作源码历史参考，最新规则与结论以本目录文件为准。安装依赖、模型与远端调用需要用户环境与授权凭据；本包不包含.env或数据库。

## 提交状态
尚未上传官网。官方要求文件夹按“团队名称-队长姓名-队长手机号-作品名称”命名；当前中性包名不含个人信息，队长确认姓名与手机号后再按官方规则重命名。绝对截止时间、大小限制以提交时官网为准。第二人独立复现尚未执行。

SHA256SUMS逐文件校验；DELIVERY_CHECKS.json记录制作核验，不是产品全功能通过证明。
