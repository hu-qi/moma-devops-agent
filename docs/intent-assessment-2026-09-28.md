# intent.py 专项评估（2026-09-28）

## 结论

把问答与仓库变更分流是合理需求；当前实现适合作为原型启发式，不适合直接决定是否允许写文件、创建 PR 或跳过交付门禁。主要问题是判定优先级、未知输入默认写入、异步覆盖规则、失败后跨意图降级。此次仅评估与离线探针，没有修改业务实现，也没有调用真实模型或发布评论。

## 已复现行为

探针通过真实 classify 执行规则；两项异步探针用 unittest.mock 替换 MoMAClient.chat_completion，验证的是仲裁代码行为，不是模型准确率。原始输入与输出见 [证据](evidence/intent-assessment-2026-09-28.json)。这是定向反例集，不能据此计算总体准确率。

| 输入 | 实际结果 | 应有处理 |
|---|---|---|
| 标题“分析登录失败原因”，正文“请修复认证逻辑并添加回归测试” | inquiry | 识别明确变更动作，计划分析→修复→验证 |
| 标题“登录异常”，正文“修复认证逻辑”，help wanted 标签 | inquiry | 标签不能覆盖正文变更请求 |
| “更新部署说明”，正文“修改 README 并提交 PR” | inquiry | 文档变更也属于仓库变更 |
| “不要修改代码，只解释 fix 的含义” | code_change | 只读问答，识别否定与被引用动作 |
| 空标题和正文 | code_change | 输入校验失败或待澄清，不默认写入 |
| “Explain address parsing” | code_change | inquiry；add 被 address 子串误命中 |
| “评估方案并落地”，正文“将缓存接入服务，补充单元测试” | inquiry | 变更或需仲裁，不能认定纯问答 |
| metadata.intent=code_change，模型返回 INQUIRY | inquiry | 可信显式覆盖不应被模型改写 |
| 模型返回 NOT_INQUIRY | inquiry | 非法枚举应拒绝，不做子串接受 |

## 按优先级的问题

### P0：副作用边界

- `routing/intent.py:128` 未知、空输入、无法识别的需求默认 CODE_CHANGE，理由却声称“要求修改”。分类推测不等于写入授权。
- `cli/main.py` 的问答异常分支只打印 warning，随后进入 AI Coding；即便分类为只读，评论失败、模型失败甚至保存状态失败也可能转为代码执行。应保留 inquiry 意图并进入可恢复失败状态，禁止跨意图 fallback。
- 可信配置应限定允许能力。分类结果只选择处理器，不能覆盖只读限制或绕过变更路径统一门禁。问答“不改代码”仍可能发布远端评论，需单独的评论授权/幂等策略。

### P1：判定正确性

- `intent.py:110–126` 标签/标题优先分支只检查标题，忽略正文已识别的变更动作。documentation、help wanted 都不能视为明确问答标签；落地、场景、说明也不是充分的只读信号。
- `_CODE_CHANGE_VERBS` 没覆盖文档、配置、测试等文件变更；无边界子串匹配导致 address 命中 add，无法处理否定、引用、混合任务。
- `intent.py:147–158` 所有 inquiry 被当成高置信度直接返回，错误问答永远不仲裁；所有 code_change 即使显式指定也送模型。同步和异步入口没有一致的优先级契约。
- `intent.py:184–189` 枚举使用子串判断，所有异常被吞掉并隐式回到 CODE_CHANGE。没有区分模型不可用、无效输出、规则未知，也没有可审计失败理由。
- `cli/main.py` 在 setup_model_environment 之前调用 classify_async；client 只读 MOMA_API_BASE，尚未归一化的 MOMA_BASE_URL/默认地址会导致仲裁失败后静默降级。分类直接依赖 os.environ 和具体 MoMAClient，也偏离已有 Provider/路由层。
- 模型指令与 Issue 全文放在同一个 user 消息，未明确分离不可信输入；应以结构化输入和独立系统指令限定任务，输出严格校验，但最终能力边界仍由代码执行。

### P2：可观测性与测试

- 返回 tuple 只有 intent/reason，无法区分 trusted override、明确规则、弱信号、模型仲裁和降级；labels 集合插值顺序也不稳定。
- 原 test_intent.py 只有7个同步正向测试，缺标题/正文冲突、否定、文档变更、空输入、异步异常和调用链副作用断言；当前统一离线 runner 未覆盖该文件。
- client 默认请求超时120秒，但分类没有独立预算、上下文截断、usage归档或总时限。to_thread 外层取消也不能自动终止正在执行的HTTP请求，需明确底层超时与取消语义。

## 建议的最小架构

保留两个业务处理器，增加“不确定”的决策状态，无需先引入复杂分类框架或更多 Agent。CODE_CHANGE 语义覆盖文档、配置和测试等所有仓库文件变更，可在兼容层保留名称。

推荐优先级：
1. 校验输入；可信 CLI/项目配置显式 intent 直接决定，非法值报错。Issue 文本不能伪装成可信 metadata。
2. 分析标题和正文的整体动作，包括否定、只读约束、引用与混合任务。标签仅作辅助信号。
3. 只有清晰无冲突的规则直接出结论；其余标记 unresolved，调用可注入的现有 MaaS 能力仲裁，严格接受枚举。
4. 模型不可用、冲突未解或输出非法时保留 unresolved，返回待澄清/人工处理；不默认提交，也不假装问答已完成。
5. 混合“评估并实施”可走变更计划的先分析后实施步骤；无需仅为混合任务新增枚举。只要求评估时只读。
6. 路由之后冻结允许动作，InquiryHandler 失败仅重试/恢复问答；每个外部评论建立 intent/结果记账，防重复。

建议结构化决策包含 intent（可空）、status（resolved/needs_clarification）、source、reason_code、matched_signals、fallback_error、policy_version。不把未经校准的模型自报 confidence 当作概率。

## 纳入现有计划

- Stage 1/C01：收集同步与异步测试，加入上述反例及现有7例；离线测试 mock 模型，不读取真实凭据。
- Stage 2/C05：先封闭默认写入与问答失败转 coding；显式覆盖不可仲裁、严格枚举、无效配置和不可用服务可见。
- Stage 3/C08–C09：注入统一 Provider/配置、结构化决策持久化、评论幂等和恢复；端到端断言 inquiry/error 分支 executor/publisher/create_change_request 调用数为0。
- Stage 4/C10：建立从真实 Issue 脱敏整理的标注集，按中文/英文、只读/变更、混合、否定、文档和标签冲突分层；报告两类误判率与待澄清率，不用单一准确率掩盖错误写入。

先补失败测试和封闭副作用边界，再修改规则/仲裁，最后校准标注集。无需在评估阶段重写整个 routing 层。
