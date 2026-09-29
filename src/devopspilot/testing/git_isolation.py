"""Shared helpers for tests and smokes that create throwaway git repositories.

These helpers MUST be used instead of bare `git init` so that temporary
repositories never inherit the reviewing machine's global Git configuration
(signature, hooks, default branch). All settings are applied with
`git config --local`, so the developer's global config is never touched.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

# Local-only config that isolates a temp repo from the host's global config.
ISOLATED_LOCAL_CONFIG: tuple[tuple[str, str], ...] = (
    ("user.name", "DevOpsPilot Test"),
    ("user.email", "devopspilot-test@example.invalid"),
    ("commit.gpgSign", "false"),
    ("core.hooksPath", "/dev/null"),  # ignore inherited global hooks
    ("init.defaultBranch", "main"),
)


def isolate_repo_config(repo: Path) -> None:
    """Apply isolated identity/signing/hooks config to an existing repo."""
    for key, value in ISOLATED_LOCAL_CONFIG:
        subprocess.run(
            ["git", "-C", str(repo), "config", "--local", key, value],
            check=True,
            capture_output=True,
            text=True,
        )


def git(*args: str, cwd: Path | None = None) -> str:
    """Run a git command in an optional directory and return stdout."""
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def init_isolated_repo(
    path: Path | None = None,
    *,
    bare: bool = False,
    initial_branch: str = "main",
) -> Path:
    """Create a new git repository pre-configured with isolated local config.

    The repo never inherits global signing/hooks/identity settings, and the
    host's global config is never modified.
    """
    if path is None:
        prefix = "devopspilot_isolated_" + ("bare_" if bare else "")
        path = Path(tempfile.mkdtemp(prefix=prefix))
    args = ["init"]
    if bare:
        args.append("--bare")
    else:
        args.extend(["-b", initial_branch])
    args.append(str(path))
    git(*args)
    if not bare:
        isolate_repo_config(path)
    return path
