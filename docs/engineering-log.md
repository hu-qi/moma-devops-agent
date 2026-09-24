# DevOpsPilot Engineering Log

## 2026-09-23

### Product Baseline

PRD v0.1 已冻结：
- DevOpsPilot —— MoMA 驱动的自进化多智能体研发交付系统
- OpenJiuwen Agent Core 作为核心 SDK / Runtime
- MoMA 作为比赛版默认 MaaS Provider
- Dynamic AgentTeam
- Self-Evolving / RSI
- DevOpsBench
- Multi-SCM / CI Provider
- Industry Engineering Packs

### Current Phase

**Technical Exploration completed for core path → Product Orchestration started**

## OpenJiuwen release/v0.1.19 line

GitHub Actions 已从 openJiuwen-ai/agent-core@release/v0.1.19 真实安装并运行。

Resolved source commit:

6f3a33fbb93aece65105c477c573057fead0e8dd

注意：当前安装后的 package metadata 仍报告 0.1.18。工程记录同时保留 source baseline 与 package metadata，不隐藏差异。

Runtime CI 已确认：
- DeepAgent
- TeamAgentSpec
- TeamEvaluator
- MemberOptimizer
- ProgramArtifactProvider
- SingleHarnessIterativeOptimizationOrchestrator
- AutoHarnessOrchestrator

## MoMA — Advanced live path VERIFIED

Basic run:
- MoMA Live Smoke / 35876800666 / success

Extended run:
- MoMA Capability Spikes / 35877219890 / success

Live verified:
- OpenAI-compatible model invocation
- DeepAgent
- Streaming: 11 chunks, MOMA_STREAM_OK
- Tool Calling: get_build_status(run_id=42)
- Dynamic AgentTeam
- RSI model/runtime injection
- token usage
- reasoning content
- response model metadata
- TTFT / generation / queue / TPS metrics

Dynamic team evidence:
- DevOps Leader
- coding-agent workspace
- review-agent workspace
- coding task assigned first
- review task independently executed after coding dependency
- team/session checkpoint persisted

Current bootstrap model:
deepseek-v4-flash-0731

MOMA_MODEL remains bootstrap/default only. Formal routing remains FAST / REASONING / CODING / REVIEW / JUDGE.

## DevOpsBench

DevOpsBench CI remains green.

Current deterministic cases include:
- coding.python.off_by_one.001
- CI working-directory failure
- SQL injection review

The next runtime integration will use a deterministic coding fixture.

## Provider Contracts — hardened

Current contract now includes:
- typed comment target: WORK_ITEM / CHANGE_REQUEST
- CI run discovery by commit SHA / source ref / status
- review objects
- CI capabilities
- trigger / cancel / logs / artifacts

Reason:
- GitHub uses one Issue-comments family for Issue and PR conversation.
- CNB exposes separate Issue/Pull comment endpoints.
- PR/MR often auto-triggers CI, so orchestration must discover rather than duplicate-trigger builds.

Latest validation:
- Core Provider Contract / 35879236115 / success
- GitHub Reference Adapter / 35879240726 / success
- CNB Reference Adapter / 35879250744 / success

## GitHub Reference Adapter

Verified:
- Repository / Issue
- PR create/read
- typed comments
- Review
- Webhook normalization + HMAC
- Actions run discovery
- job logs
- rerun failed
- trigger/cancel
- artifacts

## CNB Reference Adapter

Official Swagger mapped to:
- Repository / Issue
- Pull create/read
- Issue and Pull comments
- Review
- Build run discovery by sha/sourceRef/status
- Build status
- stage logs
- trigger
- cancel

Intentionally not claimed:
- native retry/rerun: no dedicated current OpenAPI operation found
- build artifact correlation: not yet verified
- external webhook capability: repository event history is known, external delivery not yet verified

## First DevOpsPilot product core — DeliveryLoop

Files:
- src/devopspilot/contracts/delivery.py
- src/devopspilot/orchestration/delivery_loop.py
- experiments/delivery-loop-smoke/main.py

Workflow:
- Delivery Loop / 35879543573 / success

Verified state recovery:

~~~text
CHANGE_OPENED
→ CI_PENDING
→ CI_FAILED + logs
→ REJECTED
→ later CI event
→ CI_PASSED
→ VERIFIED
~~~

The loop is event-driven/resumable and contains no hidden background polling.

## Next

Implement the runtime side of TaskExecutor:

~~~text
DeliveryTask
→ TaskProfile
→ Complexity Gate
→ Single DeepAgent or Dynamic AgentTeam
→ deterministic DevOpsBench workspace
→ code change
→ tests
→ commit
→ ExecutionResult
~~~

Only after this local deterministic path is green will remote branch publication be connected to GitHub/CNB.


## 2026-09-23 — Product Core Milestone

### OpenJiuwen TaskExecutor × DevOpsBench — LIVE VERIFIED

Workflow:

```text
OpenJiuwen Task Executor
run: 35881772137
commit: 9127f775f3d7f3c1aa8584e6db10565c5d5329b8
result: SUCCESS
```

This is the first live product-level coding execution, not merely a runtime
surface probe.

Observed evidence:

```text
OPENJIUWEN_TASK_EXECUTOR_OK
AGENTTEAM_CODE_CHANGE_OK
AGENTTEAM_REVIEW_GATE_OK
LOCAL_COMMIT_OK
DEVOPSBENCH_ORACLE_OK
```

Final validated local commit:

```text
630ba43ea1be3a5c6bc4006a0d5d9f985941f627
```

DevOpsBench reported:

```text
task_success=true
test_pass=true
```

The live AgentTeam:
- read the real deterministic fixture;
- Coding Agent changed only `range_sum.py`;
- changed `sum(range(n))` to `sum(range(n + 1))`;
- Coding Agent independently ran `python test_range_sum.py` with exit code 0;
- Review Agent independently inspected the diff;
- Review Agent independently ran the same test with exit code 0;
- Review Agent returned PASS;
- DevOpsPilot independently enforced the path allow-list/forbidden-list;
- runtime-only Python cache artifacts were removed without weakening source guards;
- DevOpsPilot created the local Git commit after AgentTeam completion;
- DevOpsBench oracle independently verified the committed candidate.

Therefore:

> MoMA + OpenJiuwen Dynamic AgentTeam + real code modification + independent
> review + deterministic evaluation is now live-proven.

### Product Core Added

The following product-owned layers are now implemented and CI-verified:

- provider-neutral `DeliveryLoop`;
- durable `DeliveryOrchestrator`;
- SQLite restart-safe delivery state with optimistic locking;
- Git worktree execution isolation;
- exact-commit `GitChangePublisher`;
- canonical delivery Trajectory;
- Trajectory → DevOpsBench runtime metrics;
- TaskProfile → capability routing;
- AgentTeam role-level routing plan;
- OpenJiuwen model-router mapping;
- GitHub reference SCM/CI adapters;
- CNB reference SCM/CI adapters.

### DevOpsBench Runtime Evidence

DevOpsBench now accepts an optional `--metrics-file`.

Observed runtime metrics can include:
- duration_ms
- model_calls
- tool_calls
- input_tokens
- output_tokens
- estimated_cost
- human_interventions
- artifacts

These metrics cannot override benchmark success. Success remains determined by
the independent oracle.

### MoMA Model Catalog — LIVE VERIFIED

Workflow:

```text
MoMA Model Catalog
run: 35883266698
result: SUCCESS
model_count: 68
```

Examples from the actual configured MoMA endpoint include:
- DeepSeek-R1-0528
- DeepSeek-V3.2
- DeepSeek-V4-Flash
- deepseek-v4.1-flash
- qwen2.5-coder-32b-Instruct
- Qwen3-32B
- Qwen3-235B-A22B
- Qwen3.5-35B-A3B
- GLM-5.3
- glm-5.3-flash
- MiniMax-M2.5
- JIUTIAN model families
- vision, embedding and rerank models

The catalog is now discovered from the live OpenAI-compatible `/models`
endpoint instead of inferred from marketing material.

### Multi-Model Runtime

The Executor now maps:

```text
DeliveryTask
   ↓
DeliveryTaskProfiler
   ↓
AgentTeamModelPlanner
   ↓
MoMAProvider
   ↓
REASONING / CODING / REVIEW RoutingDecision
   ↓
OpenJiuwen model_router
   ↓
Leader / Coding Agent / Review Agent
```

A live model-router AgentTeam run is currently the next gate.

A separate MoMA Role Model Gate is testing candidate models for the minimum
AgentTeam requirement: basic completion + OpenAI-compatible function calling.
Only models that pass the gate may become role defaults.


## 2026-09-24 — MoMA Role Capability Gate

### Action Failure Triage

Recent red/cancelled Actions were classified into distinct causes instead of being treated as one MoMA outage:

1. **Model capability mismatch**
   - `DeepSeek-R1-0528`: basic chat works, but requested function use is emitted as text/pseudo-call; no structured OpenAI `tool_calls`.
   - `qwen2.5-coder-32b-Instruct`: basic chat works, but function invocation is emitted as JSON/text rather than structured `tool_calls`.
   - These models are therefore ineligible for the current OpenJiuwen tool-using AgentTeam roles.

2. **Capability-qualified role models**
   - Leader / Reasoning: `GLM-5.3`
   - Coding: `Qwen3-32B`
   - Review: `deepseek-v4.1-flash`
   - All three passed strict live basic-chat + structured Tool Calling gates through MoMA.

3. **Expected workflow cancellation**
   - Several TaskExecutor runs were superseded by `cancel-in-progress` during rapid integration commits.
   - These are CI orchestration events, not model failures.

4. **Expected multimodal capability probe**
   - OpenJiuwen auto-probed image input against text/code models and received an expected HTTP 400.
   - The runtime correctly degraded and previous DevOpsBench execution still succeeded.
   - DevOpsPilot now explicitly sets `enable_read_image_multimodal=False` for code-only AgentTeam members.

5. **Integration defects already fixed**
   - OpenJiuwen storage type was initially configured as `inmemory`; the actual registered alias is `memory`.
   - Provider/path/runtime-cache guards were hardened through CI rather than attributed to MoMA.

### Runtime Guard

Live model evidence is now projected into:

```text
RoutingDecision.verified_features
```

Tool-using AgentTeam roles require:

```text
structured-tool-calling
```

Known-ineligible or unverified models are rejected before team execution.

### Action Noise Reduction

- Candidate model probes are report-only.
- Only selected role models use strict capability gates.
- Expensive role-model ablations are manual-only.
- TaskExecutor has a bounded overall execution timeout and phase markers.
- Trajectory workflow now supersedes stale runs.
- Future multi-file changes should prefer batch commits to reduce redundant workflow invocations.

### Next

- Complete heterogeneous AgentTeam baseline on DevOpsBench.
- Use controlled role-model ablations only among capability-qualified models.
- Capture OpenJiuwen canonical spans into DevOpsPilot `DeliveryTrajectory`.
- Use trajectory evidence for DevOpsBench metrics and RSI candidate generation.

## First Live GitHub Delivery E2E — VERIFIED

真实链路已完成：

    Issue #1
      -> MoMA + OpenJiuwen AgentTeam
      -> constrained code change
      -> local verification
      -> commit fb2e70b...
      -> branch publish
      -> PR #2
      -> GitHub E2E Fixture CI
      -> run 35907083104 SUCCESS

PR 仅修改 e2e/fixtures/github_delivery/app.py，一行修复；test_app.py 未修改。

结果指标：
- task_success = true
- runtime_clean_completion = false
- runtime_degradation_reason = agentteam_timeout

GitHub Actions 内置 GITHUB_TOKEN 可 push，但当前仓库策略禁止它创建 PR；外部 GitHub control plane 使用同一 commit 完成 PR 创建。该结果进一步验证 Execution Plane 与 SCM Control Plane 的凭据应解耦。

下一阶段：把真实 Delivery Trajectory 接入 RSI Candidate / DevOpsBench Evolution Gate。
## Team Pattern Self-Evolution Proposal — STAGED

两条独立且 task-correct 的 AgentTeam 轨迹均出现 agentteam_timeout：
- df3bf8ab84422c053ad951c8e704b7f3（DevOpsBench TaskExecutor）
- df43e104d607bd752c1d8f8d13475da5（GitHub Live E2E）

DeliveryEvolutionMiner 将其归类为 TEAM_PATTERN。

仓库当前不存在 Team/Swarm Skill，因此不错误调用 TeamSkillEvolutionRail；改用 OpenJiuwen TeamSkillCreateRail 的 repeated external evidence API。

Team Pattern Creation Proposal run 35930008850：SUCCESS。

Proposal:
- id: team_skill_evolve_create_0a84bf96ac624bf0b30fd755417088c5
- key: devopspilot-team-runtime-agentteam-timeout
- evidence_count: 2
- production_write: false

SQLiteEvolutionAuditStore 已支持 immutable TeamPatternCreationProposal，run 35930115333：SUCCESS。

官方 swarmskill-creator 已定位于 openJiuwen-ai/jiuwenswarm；后续作为外部 creator 依赖在沙箱生成候选，不复制进 DevOpsPilot 仓库。

当前停在显式人工审批门：只有用户批准后才生成 Swarm Skill candidate；仍需 DevOpsBench + RegressionGate 后才能进入 promotion。

## 2026-09-24 — Governed Evolution Infrastructure

### Real GitHub Delivery Evidence

The controlled live GitHub delivery path is verified through the exact Agent-produced commit:

~~~text
Issue #1
  → MoMA + OpenJiuwen AgentTeam
  → constrained edit
  → independent test
  → commit fb2e70b74f16859afa5ee2f015ef9e8c864353fb
  → branch devopspilot/e2e-1-35906483773
  → PR #2
  → GitHub E2E Fixture CI
  → SUCCESS
~~~

The repository policy still prevents the built-in GITHUB_TOKEN from creating a
PR directly. This is a credential/control-plane policy issue, not a delivery
execution failure.

### Team Pattern Opportunity

Repeated task-correct trajectories with AgentTeam shutdown timeout produced the
real OpenJiuwen TeamSkillCreateRail proposal:

~~~text
team_skill_evolve_create_0a84bf96ac624bf0b30fd755417088c5
~~~

The real proposal remains **PENDING_HUMAN** and has not been approved.

Synthetic approval is used only to validate candidate-generation infrastructure.

### Governed Candidate Creation

JiuwenSwarm swarmskill-creator is consumed as a pinned external dependency:

~~~text
openJiuwen-ai/jiuwenswarm
commit 6ab1ed59a8c455cdb9dfe45db34a3a8d42c10d47
~~~

The first monolithic creator experiment proved an important limitation:

~~~text
GLM-5.3
max_tokens=12000
finish_reason=length
tool_calls=None
~~~

The model correctly reasoned through the complete seven-file Swarm Skill, but
spent the output budget before emitting the giant structured tool call.

Creator V2 therefore uses staged per-file structured generation with official
file-specific JiuwenSwarm templates and one final official validator pass.

### RegressionGate

runtime_clean_completion now participates in positive improvement detection.

A Team Pattern candidate may therefore prove:

~~~text
task_success: true → true
runtime_clean_completion: false → true
~~~

without relaxing any task-success guardrail.

### Artifact Registry — CI VERIFIED

SQLiteArtifactRegistry provides:
- immutable artifact versions;
- candidate staging;
- APPROVED + gate-passed promotion only;
- active-version pointer;
- append-only activation history;
- human-approved rollback to a prior version;
- deactivate rollback for newly created Team Pattern artifacts.

Latest Evolution Artifact Registry CI: **SUCCESS**.

The registry is control-plane state only. It does not write production Skills.

### Team Pattern A/B

A manual-only live A/B harness is prepared:

~~~text
baseline:
  current dynamic Leader → Coding → Review

candidate:
  same task / models / runtime
  + validated Swarm Skill mounted through OpenJiuwen skill_use rail
~~~

Primary target:
- runtime_clean_completion improvement

Hard guardrail:
- task_success must not regress

Even a passing automated gate produces only **PENDING_HUMAN**, never automatic
production approval.
