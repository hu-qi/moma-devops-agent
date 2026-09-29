"""Smoke test for CLI demo pathways and demo-guide-and-ablation documentation."""

from __future__ import annotations

import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.cli.main import main as cli_main


def test_demo_guide_documentation_exists_and_complete() -> None:
    doc_path = ROOT / "docs" / "demo-guide-and-ablation.md"
    assert doc_path.exists(), "docs/demo-guide-and-ablation.md must exist"
    content = doc_path.read_text(encoding="utf-8")

    # Assert 3 pathways covered
    assert "Deterministic Fallback" in content
    assert "Recorded Trajectory" in content
    assert "Live E2E Execution" in content

    # Assert A0/A1/A2/A3 ablation table present
    assert "A0" in content and "Single Fast" in content
    assert "A1" in content and "Single Capable" in content
    assert "A2" in content and "Dynamic Single" in content
    assert "A3" in content and "Agent Team" in content
    assert "Single Agent First" in content
    assert "Unestimated" in content
    print("DEMO_GUIDE_DOCUMENTATION_VERIFIED_OK")


def test_cli_demo_deterministic_mode() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = cli_main(["demo", "--mode", "deterministic"])
    out = buf.getvalue()
    # C09: deterministic demo runs the real local fixture suite; no fabricated
    # "VERIFIED CLEAN" print, no invented review verdicts.
    assert exit_code == 0
    assert "Deterministic" in out
    assert "local integration fixture suite" in out
    print("CLI_DEMO_DETERMINISTIC_MODE_OK")


def test_cli_demo_recorded_mode() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = cli_main(["demo", "--mode", "recorded"])
    out = buf.getvalue()
    # C06: recorded demo shows actual archived content and its provenance,
    # not just file names.
    assert exit_code == 0
    assert "Recorded Evidence" in out
    assert "docs/evidence/" in out
    assert "Source: local archive" in out
    assert "no fabricated run summaries" in out
    print("CLI_DEMO_RECORDED_MODE_OK")


def test_cli_demo_live_mode_safe_prompt_without_tokens() -> None:
    # Ensure the no-credentials branch is actually exercised even on machines
    # whose .env provides real tokens (C01-style offline isolation for this test).
    saved = {v: os.environ.pop(v, None) for v in ("GITHUB_TOKEN", "MOMA_API_KEY")}
    old_no_dotenv = os.environ.get("DEVOPSPILOT_NO_DOTENV")
    os.environ["DEVOPSPILOT_NO_DOTENV"] = "1"
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cli_main(["demo", "--mode", "live"])
        out = buf.getvalue()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
        if old_no_dotenv is not None:
            os.environ["DEVOPSPILOT_NO_DOTENV"] = old_no_dotenv
        else:
            os.environ.pop("DEVOPSPILOT_NO_DOTENV", None)
    # C09: missing credentials is a user error -> non-zero exit with guidance,
    # never a fabricated success.
    assert exit_code != 0
    assert "Notice: Live mode requires" in out
    print("CLI_DEMO_LIVE_MODE_SAFE_PROMPT_OK")


def test_cli_live_entry_args_parse_with_target_flag() -> None:
    # C02: the live entry point must build args through the real parser using
    # the actual CLI flag (--target); the old --target-branch name must fail.
    from devopspilot.cli.main import build_parser

    args = build_parser().parse_args([
        "start", "--repo", "org/repo", "--issue", "1",
        "--mode", "single_agent", "--target", "main",
        "--db", ".devopspilot/state.db",
    ])
    assert args.target == "main"
    assert args.repo == "org/repo"
    assert args.issue == "1"
    print("CLI_LIVE_ENTRY_ARGS_PARSE_OK")


def main() -> None:
    test_demo_guide_documentation_exists_and_complete()
    test_cli_demo_deterministic_mode()
    test_cli_demo_recorded_mode()
    test_cli_demo_live_mode_safe_prompt_without_tokens()
    test_cli_live_entry_args_parse_with_target_flag()
    print("ALL DEMO CLI AND ABLATION SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
