"""Regression tests for the isolated git repo helper (R03)."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from devopspilot.testing.git_isolation import (
    ISOLATED_LOCAL_CONFIG,
    init_isolated_repo,
    isolate_repo_config,
)


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )
    return proc.stdout.strip()


def test_init_isolated_repo_sets_local_config() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = init_isolated_repo(Path(tmp) / "repo")
        for key, expected in ISOLATED_LOCAL_CONFIG:
            actual = _git("config", "--local", "--get", key, cwd=repo)
            assert actual == expected, f"{key}={actual!r}, expected {expected!r}"


def test_init_isolated_repo_main_branch() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = init_isolated_repo(Path(tmp) / "repo")
        head = _git("symbolic-ref", "HEAD", cwd=repo)
        assert head == "refs/heads/main"


def test_commit_works_with_global_gpgsign_true() -> None:
    """A commit must succeed even when global config would force signing."""
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        (home / ".gitconfig").write_text(
            "[user]\n\tname = Global User\n\temail = global@example.invalid\n"
            "[commit]\n\tgpgSign = true\n",
            encoding="utf-8",
        )
        repo = init_isolated_repo(Path(tmp) / "repo")
        (repo / "file.txt").write_text("content\n", encoding="utf-8")
        env = dict(os.environ)
        env["HOME"] = str(home)
        env["GIT_CONFIG_GLOBAL"] = str(home / ".gitconfig")
        subprocess.run(
            ["git", "add", "file.txt"],
            cwd=str(repo), env=env, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=str(repo), env=env, check=True, capture_output=True, text=True,
        )
        author = _git("log", "-1", "--format=%an <%ae>", cwd=repo)
        assert author == "DevOpsPilot Test <devopspilot-test@example.invalid>"


def test_isolate_repo_config_does_not_touch_global() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        gitconfig = home / ".gitconfig"
        gitconfig.write_text("[user]\n\tname = Keep\n", encoding="utf-8")
        repo = init_isolated_repo(Path(tmp) / "repo")
        env = dict(os.environ)
        env["GIT_CONFIG_GLOBAL"] = str(gitconfig)
        subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, 'src');"
             "from devopspilot.testing.git_isolation import isolate_repo_config;"
             f"isolate_repo_config({str(repo)!r})"],
            env=env, check=True, capture_output=True, text=True,
        )
        global_name = subprocess.run(
            ["git", "config", "--global", "--get", "user.name"],
            env={"GIT_CONFIG_GLOBAL": str(gitconfig), "PATH": os.environ["PATH"],
                 "HOME": str(home)},
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        assert global_name == "Keep"
