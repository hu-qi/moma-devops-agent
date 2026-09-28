"""Smoke test for CLI demo pathways and demo-guide-and-ablation documentation."""

from __future__ import annotations

import io
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
    assert exit_code == 0
    assert "Deterministic Fallback Mode" in out
    assert "single_agent" in out
    assert "VERIFIED CLEAN" in out
    print("CLI_DEMO_DETERMINISTIC_MODE_OK")


def test_cli_demo_recorded_mode() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = cli_main(["demo", "--mode", "recorded"])
    out = buf.getvalue()
    assert exit_code == 0
    assert "Recorded Trajectory" in out
    assert "36086881849" in out
    assert "agentteam_timeout 240s" in out
    print("CLI_DEMO_RECORDED_MODE_OK")


def test_cli_demo_live_mode_safe_prompt_without_tokens() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = cli_main(["demo", "--mode", "live"])
    out = buf.getvalue()
    assert exit_code == 0
    # Must give guidance when tokens are not present
    assert "Notice: Live mode requires" in out or "Starting live" in out
    print("CLI_DEMO_LIVE_MODE_SAFE_PROMPT_OK")


def main() -> None:
    test_demo_guide_documentation_exists_and_complete()
    test_cli_demo_deterministic_mode()
    test_cli_demo_recorded_mode()
    test_cli_demo_live_mode_safe_prompt_without_tokens()
    print("ALL DEMO CLI AND ABLATION SMOKE TESTS PASSED.")


if __name__ == "__main__":
    main()
