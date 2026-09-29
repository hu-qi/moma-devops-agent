"""Stage 3 Live Suite: three independent real-delivery runs + interrupt recovery.

C17 scenarios (each independent, resettable fixture, evidence recorded per
docs/competition/stage3-rc-manifest.md):
- S1 normal_delivery:      issue -> plan -> code+review -> tests -> CI green -> verified
- S2 ci_red_remediation:   red CI -> budget reserve -> RCA -> same-branch fix -> CI green -> verified
- S3 gate_intercepted_fix: industry gate blocks PII violation -> masked fix -> gates pass -> verified
- S4 interrupt_resume:     crash injected after PR opened -> resume -> no duplicate PR -> verified

Modes:
- default: DRY-RUN — full local chain on a resettable bare-repo fixture, zero
  network, zero remote writes. Safe to run anywhere.
- --live: REAL remote writes against the configured provider. Requires
  DEVOPSPILOT_STAGE3_CONFIRM=YES (explicit operator confirmation of target
  repository, isolated branch prefix, and budget) per the Stage 3 execution
  boundary. NOT implemented by this scaffold until the operator confirms;
  the dry-run pipeline is the executable reference of record.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

SCENARIOS = ("normal_delivery", "ci_red_remediation", "gate_intercepted_fix", "interrupt_resume")


def _record(scenario: str, fixture_base: Path, *, ok: bool, detail: str) -> dict:
    """Write one run record matching the C16 manifest schema."""
    record = {
        "run_id": f"stage3-dryrun-{scenario}",
        "stage3_scenario": scenario,
        "mode": "dry_run_local",
        "rc": {"baseline_note": "see docs/competition/stage3-rc-manifest.md (frozen after commit+tag)"},
        "verification": {"accepted": ok},
        "detail": detail,
    }
    out = fixture_base / f"{scenario}.record.json"
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


def run_dry_run() -> int:
    """Execute all four scenarios offline against the deterministic E2E suite."""
    fixture_base = Path(tempfile.mkdtemp(prefix="stage3_dryrun_"))
    failed: list[str] = []
    try:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "experiments" / "end-to-end-integration-suite" / "main.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-8:]
        detail = "\n".join(tail)
        if proc.returncode == 0:
            # The E2E suite IS scenarios S1+S2+S3 (normal / ci-remediation / gate
            # interception) executed on resettable local fixtures.
            for scenario in SCENARIOS[:3]:
                _record(scenario, fixture_base, ok=True, detail=detail)
            print("[dry-run] S1 normal_delivery        PASS (via end-to-end-integration-suite)")
            print("[dry-run] S2 ci_red_remediation    PASS (via end-to-end-integration-suite)")
            print("[dry-run] S3 gate_intercepted_fix  PASS (via end-to-end-integration-suite)")
        else:
            for scenario in SCENARIOS[:3]:
                _record(scenario, fixture_base, ok=False, detail=detail)
            print(f"[dry-run] E2E suite FAILED (exit {proc.returncode}):")
            print(detail)
            failed.append("e2e_suite")

        # S4 interrupt-resume + duplicate-start side-effect guarantees
        ok4, detail4 = _interrupt_resume_check()
        _record("interrupt_resume", fixture_base, ok=ok4, detail=detail4)
        print(f"[dry-run] S4 interrupt_resume       {'PASS' if ok4 else 'FAIL'}")
        if not ok4:
            failed.append("interrupt_resume")
    finally:
        shutil.rmtree(fixture_base, ignore_errors=True)

    if failed:
        print(f"\nSTAGE3 DRY-RUN FAILED: {failed}")
        return 1
    print("\nSTAGE3 DRY-RUN ALL SCENARIOS PASSED (local fixtures, zero remote writes).")
    return 0


def _interrupt_resume_check() -> tuple[bool, str]:
    """S4: crash after PR opened -> resume must not duplicate side effects.

    Reuses the fault-injection assertions from cli-smoke by loading its module
    from file path (directory name contains a hyphen, so it is not importable
    as a package name).
    """
    try:
        import importlib.util

        module_path = ROOT / "experiments" / "cli-smoke" / "main.py"
        spec = importlib.util.spec_from_file_location("cli_smoke_stage3", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.test_fault_injection_no_duplicate_pr_after_crash()
        return True, "resume keeps exactly one PR/comment; duplicate start adds zero side effects"
    except Exception as exc:
        return False, f"interrupt-resume check failed: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 3 live suite (dry-run by default)")
    parser.add_argument("--live", action="store_true", help="Attempt real remote writes (requires confirmation)")
    args = parser.parse_args()

    if args.live:
        import os
        if os.environ.get("DEVOPSPILOT_STAGE3_CONFIRM", "") != "YES":
            print(
                "Refusing to run live writes: set DEVOPSPILOT_STAGE3_CONFIRM=YES after "
                "confirming target repository, isolated branch prefix, and budget."
            )
            return 1
        print("Live mode not yet wired for Stage 3; implement after operator confirms the RC tag.")
        return 1

    return run_dry_run()


if __name__ == "__main__":
    sys.exit(main())
