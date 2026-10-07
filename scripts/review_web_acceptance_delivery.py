#!/usr/bin/env python3
"""Post-publication independent review of the first Web acceptance fixture.

The original run lacked a typed Review. This audit explicitly records that the
review happened AFTER publication; it must never be described as a pre-publish gate.
"""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from devopspilot.cli.main import load_dotenv_if_present  # noqa: E402
from devopspilot.adapters.moma.client import MoMAClient  # noqa: E402
from devopspilot.adapters.moma.review import review_diff  # noqa: E402
from devopspilot.persistence.sqlite_state import SQLiteDeliveryStateStore  # noqa: E402
from devopspilot.trajectory.persistent_store import FileTrajectoryStore  # noqa: E402
from devopspilot.evaluation.metrics import trajectory_runtime_metrics  # noqa: E402


async def main():
    load_dotenv_if_present(ROOT / ".env")
    evidence_path = ROOT / "docs/evidence/web-console-delivery.json"
    evidence = json.loads(evidence_path.read_text())
    delivery_id = evidence["delivery_id"]
    store = SQLiteDeliveryStateStore(
        os.environ.get("DEVOPSPILOT_DB_PATH", "devopspilot.db")
    )
    stored = await store.load(delivery_id)
    execution = stored.state.execution
    if execution.review:
        print(
            json.dumps(
                {
                    "review_already_exists": True,
                    "verdict": execution.review.verdict.value,
                }
            )
        )
        return
    workspace = Path(execution.metadata["workspace_path"])

    def run(cmd):
        return subprocess.run(
            cmd, cwd=workspace, capture_output=True, text=True, check=True
        ).stdout

    if run(["git", "rev-parse", "HEAD"]).strip() != execution.commit_sha:
        raise ValueError("Workspace HEAD differs from the published commit")
    diff = run(
        [
            "git",
            "diff",
            execution.metadata["base_commit"],
            execution.commit_sha,
            "--",
            ".",
        ]
    )
    paths = run(
        [
            "git",
            "diff",
            "--name-only",
            execution.metadata["base_commit"],
            execution.commit_sha,
        ]
    ).splitlines()
    if set(paths) - {
        "e2e/fixtures/github_delivery/app.py",
        "e2e/fixtures/github_delivery/test_app.py",
    }:
        raise ValueError("Acceptance diff changed files outside the authorized fixture")
    subprocess.run(
        [sys.executable, "test_app.py"],
        cwd=workspace / "e2e/fixtures/github_delivery",
        capture_output=True,
        text=True,
        check=True,
    )
    trajectories = FileTrajectoryStore(
        Path(os.environ.get("DEVOPSPILOT_DB_PATH", "devopspilot.db")).resolve().parent
        / "trajectories"
    )
    trajectory = await trajectories.load(execution.metadata["trajectory_id"])
    review, events = await asyncio.to_thread(
        review_diff,
        MoMAClient(),
        model=os.environ["MOMA_REVIEW_MODEL"],
        diff=diff,
        test_summary="Independent fixture test_app.py returned exit 0.",
        sequence=max(e.sequence for e in trajectory.events) + 1,
    )
    review = replace(
        review,
        commit_sha=execution.commit_sha,
        metadata={
            **review.metadata,
            "audit_timing": "post_publication",
            "original_missing_review": "true",
        },
    )
    trajectory = replace(trajectory, events=trajectory.events + events)
    await trajectories.save(trajectory)
    metrics = trajectory_runtime_metrics(trajectory)
    execution = replace(
        execution,
        review=review,
        metadata={
            **execution.metadata,
            "review_audit_timing": "post_publication",
            "trajectory_event_count": str(len(trajectory.events)),
            **{
                k: str(metrics[k])
                for k in ("model_calls", "tool_calls", "input_tokens", "output_tokens")
            },
        },
    )
    await store.save(
        delivery_id,
        replace(stored.state, execution=execution),
        expected_version=stored.version,
    )
    evidence.update(
        delivery_id=delivery_id,
        commit_sha=execution.commit_sha,
        pr_url=stored.state.change_request.web_url,
        independent_review={
            "verdict": review.verdict.value,
            "model": review.metadata["model"],
            "diff_digest": review.diff_digest,
            "created_at": review.created_at,
            "audit_timing": "post_publication",
            "summary": review.summary,
        },
        runtime_degraded=True,
    )
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
