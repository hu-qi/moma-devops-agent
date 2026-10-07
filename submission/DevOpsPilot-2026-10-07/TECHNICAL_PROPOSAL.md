# DevOpsPilot 技术方案书

基线 7076541e445a9f2da365b52fce74cf6df3c4ff17

## 作品概述

作品名称 DevOpsPilot；参赛团队 CodeArts；赛道 2026模型应用赛。作品面向研发维护人员，将真实 Issue 接入、模型执行、代码变更、独立审查、PR、CI 与交付证据连接到一个本机 Web 工作台。

目前可展示真实项目查询、持久化流水线和一次受控 GitHub fixture 交付。现有实现由本地源码、41项离线检查、24个题库预置验证，以及实际 PR 和 CI 支持。当前版本为提交材料基线，不宣称已达到生产级自治交付或完成所有 PRD 签收。

目标用户为有代码仓库与CI基础设施的研发团队、DevOps工程师和开源维护者。首先验证小规模、可回滚、路径可约束的维护任务；政务与金融行业规则包作为工程示例，不能替代法规认证。

## 用户场景与能力设计

典型路径为操作员接入项目并设置可信测试命令与路径边界，在需求中心同步真实Issue，显式选择任务与意图，提交后台执行，观察VOD、Issue、Coding、QA、SRE五阶段，检查代码、审查、CI链接并下载证据。阶段卡片是交付状态视图，不代表五个常驻独立智能体。

项目配置与Issue内容分离。任务正文不能覆盖可信测试命令、允许修改路径、禁止路径和required checks。后台任务持久化，重复启动去重；已有交付使用resume继续，服务重启留下的作业显示interrupted。

一次性预约由本机服务调度，可取消；Chat调用真实MoMA并展示实际usage。知识库读取仓库Markdown，技能页读取行业Pack，题库页读取真实case.json。未配置的IM和未接入的CNB Live执行明确标为未接入。

## 系统架构与移动云模型分工

Web和CLI是接入层。ConsoleService读取canonical SQLite交付payload，并使用旁路console数据库保存项目、作业、预约和问答。控制面负责意图、计划、预算、状态与恢复；执行适配器承接OpenJiuwen运行；SCM和CI适配器读取或写入真实平台；验证器决定verified、rejected、pending与degraded。

MoMA使用统一API入口。当前配置：deepseek-v4.1-flash用于快速角色及独立Review，GLM-5.3用于推理与Judge，Qwen3-32B用于Coding及Evolution。材料不包含API密钥，不假设配置模型即等于每个事件实际调用模型；真实模型调用以轨迹与usage为准。

OpenJiuwen负责智能体与工具运行，MoMA提供模型推理，DevOpsPilot控制面负责可信配置、持久化与交付判定。现有Runtime版本由requirements-runtime.txt固定；框架运行异常与业务任务成功分别记录。GitHub和AtomGit有Live装配，平台CI能力差异保留，不把AtomGit描述为原生Actions。

## Prompt策略 工具设计与审查门禁

执行上下文包含目标、任务来源、仓库状态、允许路径、测试命令与预算。提示明确要求读取代码、做最小修改、执行测试、停止无关任务板循环；但提示并非权限隔离。路径验证与执行后检查在宿主侧执行，工作目录不能被视为安全沙箱。

独立Reviewer为只读模型调用，收到实际最终diff与独立测试结果。system prompt把diff和测试文本视为不可信数据，要求返回结构化approved/rejected、summary、findings；宿主计算diff摘要并生成审查时间。严格Live启动强制require_review，缺失、拒绝、格式错误或diff不匹配阻断提交。

SCM发布通过持久化状态与幂等意图控制；CI验证需关联真实提交与required checks。预算在失败执行中消耗，超限升级人工。工具超时与取消清理进程组。当前控制台仅面向可信本机操作员，未提供多用户认证、RBAC或公网服务。

## 真实交付结果与证据边界

2026年10月7日经Web启动GitHub Issue #7：Add fixture status metadata。操作范围仅为e2e/fixtures/github_delivery/app.py与test_app.py，保留原status行为并增加status_metadata和断言。真实PR #8保持未合并，交付commit为105d74d7fe03f33163dde036ce1d4abba960a3c7。

GitHub Actions run 37601566835在上述提交上成功；独立fixture测试退出码0。审查模型deepseek-v4.1-flash返回approved，diff摘要ceebbaf775d5cdab6fb0946437d962569f35d40bc26c0e92e27ab3ab5cedc26d。

该首次运行产生有效代码后，AgentTeam未干净结束而达到超时边界。原执行遗漏前置审查，随后进行了真实发布后补审。最终状态verified_degraded，task_success=true、runtime_clean_completion=false。严格Live门禁现已修复，完整修复后Live重跑尚未完成；不能将补审作为原发布前审查成功证据。

PR链接 https://github.com/hu-qi/moma-devops-agent/pull/8 。CI链接 https://github.com/hu-qi/moma-devops-agent/actions/runs/37601566835 。原始摘要位于evidence/web-console-delivery.json。

## 效果评估与可复算方法

当前完整离线检查为41项，最新已留存运行结果41通过、0失败、19.65秒。这是受控环境组件回归结果，不是41个真实业务任务的成功率。当前24个DevOpsBench案例分为coding、code-review、ci-debug各8例，其中每类2例holdout，共6例。

本次运行validate-fixtures得到24通过、0失败。该命令验证初始缺陷与oracle契约有效，不调用模型，也不证明Agent修复成功。完整A0–A3同题同预算重复实验没有完整原始结果可用于正式比较，因此不报告成功率提升、降本百分比或统计显著性。

后续冻结RC、模型、题库和预算后，按24例×4策略×3次生成至少288条原始记录，保留失败样本，按类别与holdout分组重算成功率、耗时、tokens、人工介入与运行健康。价格未经核实记unestimated。方法与当前事实报告见EVALUATION_REPORT.md。

## 商业价值与产品RoadMap

商业价值假设：团队可减少在Issue、代码、PR、CI与日志之间的切换，保留审查与恢复证据，帮助人工判断是否接受交付。潜在客户为已有代码托管与CI的企业研发部门；适合先从内部维护任务试点。当前没有正式付费客户、用户访谈结论或ROI实测，不把市场假设写成收益成果。

拟议商业模式为私有化部署与支持、团队级订阅及行业Pack服务。定价需通过试点确认调用成本、交付成功率、人工复核时间和部署成本后制定。MoMA价值在于统一接入与多模型配置；本作品尚未独立测量MoMA相对其他平台的价格或时延优势。

RoadMap按验收推进：提交基线为材料与证据可携带；稳定版修复Runtime终止并完成前置Review Live重跑；V1完成CI红转绿、行业Gate与中断恢复签收；评测版完成288条原始记录和受控进化正反例；企业试点再补认证、隔离、Webhook运营与成本治理。具体依赖、角色与验收见ROADMAP.md。

## 部署复现与提交说明

源码包固定到7076541e445a9f2da365b52fce74cf6df3c4ff17，不包含.env、数据库、虚拟环境、工作目录或私密运行日志。Python 3.11为建议运行环境；安装核心、测试与固定Runtime依赖后执行离线检查。无凭据路径只验证离线行为，Live需要操作员在本地提供MoMA与SCM凭据。

启动命令为.venv/bin/python scripts/serve_dashboard.py --port 8080；浏览器访问http://127.0.0.1:8080。联网演示读取真实缓存与API，断网使用随包交付的真实证据HTML回放。视频采用真实页面截图证据回放，含合成中文旁白和字幕，不冒充连续Live操作录屏。

官方页面已确认模型应用赛使用附件2统一PPT模板；五项内容已映射到本套材料。作品按团队名称-队长姓名-队长手机号-作品名称命名目录后压缩，由队长上传。团队名称CodeArts已在登录页面读取；完整队长姓名与手机由人类最后核对，公开目录暂不包含个人信息。

官方上传页本次显示剩余约7天15小时，未展示绝对截止时间、文件大小或视频时长上限。提交前需核对实时倒计时与系统限制；本包不臆造这些限制。成员审核、原创性声明、账户身份及最终提交由团队确认。
