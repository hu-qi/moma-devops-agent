# Stage 3 发布候选（RC）清单与 Run 记录规范

对应任务：`docs/competition/TODO.md` C16。基线日期：2026-09-29。

## 1. 发布候选标识（待冻结）

| 项 | 值 | 状态 |
|---|---|---|
| 基线 commit（HEAD） | `e9c2021211b7b43ada1244c8c5f40cf81d19a986` | ⚠️ 工作区含 Stage 1/2 未提交修改（CI 配置、README、CLI、smoke 等），**正式 RC 必须在提交并打 tag 后冻结**，不得用脏工作区冒充 RC |
| Python | 3.14.7（本地）；CI 使用 3.11 | 记录双值，Live 以实际运行值为准 |
| Runtime | openjiuwen `release/v0.1.19` @ `6f3a33fbb93aece65105c477c573057fead0e8dd`（见 `pyproject.toml` runtime extra） | 已固定 |
| 行业 Pack | `devopspilot-industry-government` v0.1.0（`industry-packs/government/pack.yaml`，digest 由 `compute_digest()` 计算） | 已固定 |
| 评测案例 | `benchmarks/cases/`（以提交版本为准） | 待冻结 |
| MoMA 模型 | coding=`Qwen3-32B`，review=`deepseek-v4.1-flash`（默认值，可被 `MOMA_CODING_MODEL`/`MOMA_REVIEW_MODEL` 覆盖；每次 run 记录实际值） | 记录于每次 run |

**冻结流程**：Stage 1/2 修改提交 → 在该 commit 打 tag（如 `rc-stage3`）→ 回填本表 SHA → Live 三轮必须从该 tag 运行。

## 2. 每次 Live Run 必须记录的字段

JSON 结构（写入 `docs/evidence/` 归档，命名 `stage3-run-<n>-<日期>.json`）：

```json
{
  "run_id": "由 CLI/CI 生成的唯一 id",
  "stage3_scenario": "normal_delivery | ci_red_remediation | gate_intercepted_fix | interrupt_resume",
  "rc": {
    "git_sha": "", "git_tag": "", "python_version": "", "runtime_commit": "",
    "industry_pack": {"pack_id": "", "version": "", "digest": ""}
  },
  "task": {"repository": "", "issue_id": "", "delivery_id": "", "intent_decision": {}},
  "planning": {"mode": "single_agent|agent_team", "rationale": "", "plan_json": ""},
  "models": {"coding_model": "", "review_model": "", "tokens_input": 0, "tokens_output": 0},
  "execution": {"elapsed_seconds": 0.0, "commit_sha": "", "source_branch": "", "review_verdict": "", "review_model": ""},
  "tests": {"command": "", "returncode": 0, "summary_tail": ""},
  "ci": {"run_id": "", "status": "", "conclusion": "", "commit_sha": "", "required_checks": []},
  "remediation": [{"attempt": 1, "action": "", "outcome": "", "resulting_commit_sha": ""}],
  "verification": {"accepted": false, "outcome_status": "", "evidence": []},
  "trajectory": {"id": "", "event_count": 0, "disk_file": ""},
  "human_intervention": {"required": false, "reason": "", "actions": []},
  "degradation": {"flagged": false, "reason": ""}
}
```

字段来源全部为持久化 state/report/CLI 输出，禁止手工宣称。价格未知记 `unestimated`，不得记为免费。

## 3. 执行边界（Stage 3 全程有效）

- 先只读检查与 dry-run；远端写入（真实 Issue/PR/CI）须确认目标仓库、隔离分支与预算后执行。
- 三轮 Live 与中断恢复的脚本见 `experiments/stage3-live-suite/`（C17 准备，dry-run 先行）。
- 历史成功（如 GitHub run `36086881849`）不得冒充当前 RC 的签收证据。
