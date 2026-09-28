"""Smoke test for fixture lifecycle, bootstrap contract, and namespace isolation."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from e2e.fixtures.ci_remediation.reset import BROKEN_SOURCE, is_reset, reset_fixture


def test_fixture_idempotent_reset() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="devopspilot_fixture_test_"))
    try:
        app = tmp / "app.py"
        app.write_text("def status(): return 'fixed'\n", encoding="utf-8")
        assert not is_reset(tmp)

        # First reset -> should change
        changed1 = reset_fixture(tmp)
        assert changed1 is True
        assert is_reset(tmp)
        assert app.read_text(encoding="utf-8") == BROKEN_SOURCE

        # Second reset -> idempotent, should not change
        changed2 = reset_fixture(tmp)
        assert changed2 is False
        assert is_reset(tmp)
        print("FIXTURE_IDEMPOTENT_RESET_OK")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_namespace_protection_guards() -> None:
    target_branch = "devopspilot/fixture-ci-remediation"
    protected_branches = {"main", "master", target_branch, "devopspilot/fixture-ci-remediation"}

    def is_safe_to_delete(branch: str) -> bool:
        return (
            branch.startswith("devopspilot/")
            and branch not in protected_branches
        )

    assert not is_safe_to_delete("main")
    assert not is_safe_to_delete("master")
    assert not is_safe_to_delete("devopspilot/fixture-ci-remediation")
    assert not is_safe_to_delete("feature/user-auth")
    assert is_safe_to_delete("devopspilot/remediation-candidate-123")
    assert is_safe_to_delete("devopspilot/e2e-4-36086881849")
    print("NAMESPACE_PROTECTION_GUARDS_OK")


def test_bootstrap_missing_branch_contract() -> None:
    # Simulates local git repository bootstrap when target branch is missing
    tmp_repo = Path(tempfile.mkdtemp(prefix="devopspilot_git_repo_"))
    try:
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "DevOpsPilot"], cwd=tmp_repo, check=True)
        subprocess.run(["git", "config", "user.email", "devopspilot@local"], cwd=tmp_repo, check=True)

        # Create initial commit on main
        dummy_file = tmp_repo / "README.md"
        dummy_file.write_text("# Repo\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_repo, check=True, capture_output=True)

        target_branch = "devopspilot/fixture-ci-remediation"

        # Check branch existence
        branch_exists = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"],
            cwd=tmp_repo,
        ).returncode == 0
        assert not branch_exists

        # Bootstrap: checkout -B target_branch from main
        subprocess.run(["git", "checkout", "-B", target_branch, "main"], cwd=tmp_repo, check=True, capture_output=True)

        # Setup fixture
        fixture_dir = tmp_repo / "e2e" / "fixtures" / "ci_remediation"
        reset_fixture(fixture_dir)
        assert is_reset(fixture_dir)

        subprocess.run(["git", "add", "."], cwd=tmp_repo, check=True)
        subprocess.run(["git", "commit", "-m", "chore: bootstrap fixture"], cwd=tmp_repo, check=True, capture_output=True)

        branch_exists_after = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{target_branch}"],
            cwd=tmp_repo,
        ).returncode == 0
        assert branch_exists_after
        print("BOOTSTRAP_MISSING_BRANCH_CONTRACT_OK")
    finally:
        shutil.rmtree(tmp_repo, ignore_errors=True)


def main() -> None:
    test_fixture_idempotent_reset()
    test_namespace_protection_guards()
    test_bootstrap_missing_branch_contract()
    print("ALL FIXTURE LIFECYCLE TESTS PASSED.")


if __name__ == "__main__":
    main()
