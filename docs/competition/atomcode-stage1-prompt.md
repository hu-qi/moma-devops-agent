你在 /Users/huqi/Develop/todo/test/moma-devops-agent 工作。用户明确要求由 atomcode -y 使用 gemini-gw/gemini-3.8-flash-medium 推进移动云杯完整作品。现在执行 IMPLEMENTATION_PLAN.md 的 Stage 1（C01–C07），不要只提出建议。阅读 docs/competition/TODO.md 和仓库 AGENTS.md（若存在），先理解已有实现，写行为回归测试再最小修复。

规则：
1. 当前只完成 Stage 1，避免同时修改后续阶段业务。历史评估不可抹除；完成状态必须有当前证据。
2. 避免凭据读取/打印，禁止上传 .env 或配置文件。模型调用仅用于本次编码助手；禁止触发产品 Live、远端 push/PR/Issue/评论、部署或比赛提交。
3. 可以创建本地临时虚拟环境、安装项目现有 test 依赖并运行离线测试。保持项目既有框架。允许临时 fixture 禁用签名，不得 --no-verify 或禁用测试。
4. 修复 live demo 参数；GitHub get_work_item 契约及真实任务读取失败的阻断；统一 pytest tests/ 收集和 CI 触发；修正文档安装；recorded 展示已有真实 artifact 内容/出处，缺证据明示，不捏造；明确 pending/failed/verified 输出与退出语义。
5. 使用不同于真实凭据的 stub 和 monkeypatch 测试，不访问外部业务平台。新增测试验证行为而非仅查源码字符串。
6. 每问题三次失败后停下该问题、记下错误与替代方案，可继续不受影响的独立任务。
7. 完成后运行相关测试和统一离线套件；更新 docs/competition/TODO.md 证据和 IMPLEMENTATION_PLAN.md 状态；写 docs/competition/stage1-execution-report.md，列文件、命令、结果、未完成项、风险。不可把后续阶段标完成。
8. 只在验证通过后进行本地增量 commit，不推送；不要提交无关已有改动。最终报告 commit SHA。不要自行启动其他代理。
