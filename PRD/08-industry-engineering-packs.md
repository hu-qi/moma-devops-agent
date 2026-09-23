# 08 — Industry Engineering Packs

## 1. Positioning

DevOpsPilot 是横向研发智能底座。

行业能力通过 **Industry Engineering Pack** 插入，而不是修改 Core。

```text
DevOpsPilot Core
   ├── Government Pack
   ├── Finance Pack
   ├── Industrial Pack
   └── Healthcare Pack
```

## 2. What an Industry Pack Contains

建议结构：

```text
industry-packs/<industry>/
├── knowledge/
├── rules/
├── skills/
├── prompts/
├── team-patterns/
├── tests/
└── evals/
```

内容包括：
- Domain engineering knowledge
- compliance rules
- architecture constraints
- secure coding rules
- testing gates
- review checklist
- documentation requirements
- Team Pattern
- benchmark cases

## 3. Boundary

Industry Pack 用于指导“行业软件如何开发得更正确”。

不用于替代：
- 医疗诊断
- 金融投资决策
- 政务行政裁量
- 工业安全关键控制决策

## 4. Government Pack Examples

可探索：
- 信创适配
- 等保相关软件工程约束
- 权限、审计、留痕
- 国产化依赖检查
- 政务流程系统测试门禁

## 5. Finance Pack Examples

可探索：
- 敏感字段处理
- 审计日志
- 权限隔离
- 交易类操作幂等
- 高风险接口 Review
- 数据合规检查

## 6. Industrial Pack Examples

可探索：
- OT/IT 边界
- 工业协议适配
- 边缘设备与离线场景
- 高可用
- 兼容性测试
- 安全边界

## 7. Healthcare Pack Examples

可探索：
- 医疗数据隐私
- 数据脱敏
- 审计
- 医疗信息系统接口规范
- 高风险数据操作测试

具体规则必须基于可靠公开标准或客户授权规则，不能由模型自行编造。

## 8. Pack Selection

Task Context 中加入：

```text
industry
organization
project
repo
```

加载顺序建议：

```text
Core Policy
  ↓
Industry Pack
  ↓
Organization Rules
  ↓
Project Rules
  ↓
Task Context
```

越具体的规则可覆盖更通用的策略，但不能突破安全上限。

## 9. Evolution

Industry Pack 可以通过真实项目轨迹产生 Candidate，但：
- 行业规范与合规基线不可由在线模型无审批改写。
- 可进化的是工程执行策略、Skill、Checklist、Team Pattern。
- 标准/法规来源必须具备 provenance。

## 10. Competition Strategy

比赛阶段不需要同时完成四个行业 Pack。

建议选一个代表性行业做深 Demo，并证明 Core 可扩展到其他行业。

具体首个行业在完成行业价值与数据可得性调研后决定。
