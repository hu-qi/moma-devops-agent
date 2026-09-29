# Stage 3 发布候选（RC）清单与 Run 记录规范

对应任务：`docs/competition/TODO.md` C16。基线日期：2026-09-29。

## 1. 发布候选标识（待冻结）

| 项 | 值 | 状态 |
|---|---|---|
| 基线 commit（HEAD） | Phase A（R01–R05）完成后冻结，见下方 RC 表 | 冻结见下 |
| Python | 3.11.14（本地）；CI 使用 3.11 | 记录双值，Live 以实际运行值为准 |
| Runtime | openjiuwen `release/v0.1.19` @ `6f3a33fbb93aece65105c477c573057fead0e8dd`（见 `pyproject.toml` runtime extra） | 已固定 |
| 行业 Pack | `devopspilot-industry-government` v0.1.0（`industry-packs/government/pack.yaml`） | 已固定 |
| 评测案例 | `benchmarks/cases/` 9 例（case.json 聚合 SHA256 `b2c27dbb2f175d1406ce26e81fea9dfbb7c8c9c99a8459ada396a07b81495aed`） | 已冻结（R06） |
| 行业 Pack digest | `fecd034c750574766ce8feef277435fe8c91d2db8bc9666777a40cef54b4d984`（SHA256） | 已冻结（R06） |
| MoMA 模型 | coding=`Qwen3-32B`，review=`deepseek-v4.1-flash`（默认值，可被 `MOMA_CODING_MODEL`/`MOMA_REVIEW_MODEL` 覆盖；每次 run 记录实际值） | 记录于每次 run |

**冻结流程**：Stage 1/2 修改提交 → 在该 commit 打 tag（如 `rc-stage3`）→ 回填本表 SHA → Live 三轮必须从该 tag 运行。

### RC 冻结记录（R06，2026-09-30）

- **Tag**：`rc-2026-mobile-cloud-cup-01`（后续代码变更必须生成 `-02`，不得移动旧 tag）
- **RC commit SHA**：冻结提交后在下方回填真实 SHA
- **Phase A 状态**：R01–R05 已完成（pytest-asyncio 依赖闭环、CI workflow 修正、Git 全局配置隔离、pytest 收集语义统一、Live 脚本退出码与业务结果绑定）
- **Required workflows**：`Offline Regression and Gates` 对该 SHA 的 run URL 待推送后回填
- **验证命令与结果**：`python scripts/run_offline_checks.py` → `41 passed, 0 failed`（本地 Python 3.11.14）；空 venv `pip install -e ".[test]"` 后 pytest 21 passed（R01 证据 `/tmp/r01_pip_freeze.txt`、`/tmp/r01_offline.log`）

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
