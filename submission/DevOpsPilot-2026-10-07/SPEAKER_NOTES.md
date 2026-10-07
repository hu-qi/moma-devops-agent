# 答辩讲稿

## 1 DevOpsPilot

作品重点是把模型执行连接到可审查的研发交付。所有效果声明只引用本包证据。

## 2 答辩内容

对应官方作品要求五项内容：简介、能力、技术、评估、商业价值。

## 3 Agent简介

作品名称 DevOpsPilot；参赛团队 CodeArts；赛道 2026模型应用赛。作品面向研发维护人员，将真实 Issue 接入、模型执行、代码变更、独立审查、PR、CI 与交付证据连接到一个本机 Web 工作台。

## 4 能力设计与真实 Web

五阶段是产品状态视图，不承诺五个常驻独立Agent。截图来自本机真实数据库。

## 5 技术架构与模型分工

Web和CLI是接入层。ConsoleService读取canonical SQLite交付payload，并使用旁路console数据库保存项目、作业、预约和问答。控制面负责意图、计划、预算、状态与恢复；执行适配器承接OpenJiuwen运行；SCM和CI适配器读取或写入真实平台；验证器决定verified、rejected、pending与degraded。

## 6 Prompt与工具策略

执行上下文包含目标、任务来源、仓库状态、允许路径、测试命令与预算。提示明确要求读取代码、做最小修改、执行测试、停止无关任务板循环；但提示并非权限隔离。路径验证与执行后检查在宿主侧执行，工作目录不能被视为安全沙箱。 独立Reviewer为只读模型调用，收到实际最终diff与独立测试结果。system prompt把diff和测试文本视为不可信数据，要求返回结构化approved/rejected、summary、findings；宿主计算diff摘要并生成审查时间。严格Live启动强制require_review，缺失、拒绝、格式错误或diff不匹配阻断提交。

## 7 交付门禁与恢复

工作目录不是权限沙箱。当前版本是可信本机操作员控制台，暂无企业认证/RBAC。

## 8 真实交付结果

2026年10月7日经Web启动GitHub Issue #7：Add fixture status metadata。操作范围仅为e2e/fixtures/github_delivery/app.py与test_app.py，保留原status行为并增加status_metadata和断言。真实PR #8保持未合并，交付commit为105d74d7fe03f33163dde036ce1d4abba960a3c7。 该首次运行产生有效代码后，AgentTeam未干净结束而达到超时边界。原执行遗漏前置审查，随后进行了真实发布后补审。最终状态verified_degraded，task_success=true、runtime_clean_completion=false。严格Live门禁现已修复，完整修复后Live重跑尚未完成；不能将补审作为原发布前审查成功证据。 来源 evidence/web-console-delivery.json

## 9 效果评估

41项是组件回归，24项是fixture初始契约验证，均不能当作真实业务修复成功率。来源EVALUATION_REPORT.md。

## 10 商业价值与试点路径

尚无付费客户和ROI实测。商业模式是拟议方案，不是已取得商业成果。

## 11 产品RoadMap

所有未来里程碑按证据验收，不将计划标为完成。详细角色、依赖与退出条件见ROADMAP.md。

## 12 感谢您的观看

最终是否提交由队长核对官方规则、团队信息和运行边界后确认。
