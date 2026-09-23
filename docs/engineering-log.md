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
