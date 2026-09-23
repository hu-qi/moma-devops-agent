"""Publish a validated local commit to an already-authenticated Git remote."""

from __future__ import annotations

import asyncio
import shlex
from dataclasses import replace
from pathlib import Path

from devopspilot.contracts.delivery import DeliveryTask, ExecutionResult


async def _git(*args: str, cwd: Path) -> str:
    process = await asyncio.create_subprocess_exec(
        "git",
        *args,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        command = "git " + " ".join(shlex.quote(x) for x in args)
        raise RuntimeError(
            f"{command} failed ({process.returncode}): "
            f"{stderr.decode('utf-8', errors='replace')}"
        )
    return stdout.decode("utf-8", errors="replace").strip()


class GitChangePublisher:
    """Push the exact validated commit to a configured remote branch.

    Authentication is intentionally outside this class. Workspace preparation
    is responsible for configuring an authenticated Git remote/credential
    helper. This keeps provider secrets out of ExecutionResult and command args.
    """

    def __init__(self, *, remote: str = "origin") -> None:
        self._remote = remote

    async def publish(
        self,
        task: DeliveryTask,
        result: ExecutionResult,
    ) -> ExecutionResult:
        if result.published:
            return result

        workspace_value = result.metadata.get("workspace_path")
        if not workspace_value:
            raise ValueError("ExecutionResult.metadata.workspace_path is required")
        workspace = Path(workspace_value)
        if not workspace.is_dir():
            raise FileNotFoundError(f"Execution workspace not found: {workspace}")

        head = await _git("rev-parse", "HEAD", cwd=workspace)
        if head != result.commit_sha:
            raise RuntimeError(
                f"Workspace HEAD {head} does not match validated commit {result.commit_sha}"
            )

        status = await _git("status", "--porcelain", cwd=workspace)
        if status:
            raise RuntimeError("Refusing to publish a dirty execution workspace")

        remote_url = await _git("remote", "get-url", self._remote, cwd=workspace)
        if not remote_url:
            raise RuntimeError(f"Git remote {self._remote!r} is not configured")

        await _git(
            "push",
            self._remote,
            f"{result.commit_sha}:refs/heads/{result.source_branch}",
            cwd=workspace,
        )

        # Resolve the remote ref and prove the validated commit identity survived
        # the side effect.
        remote_head = await _git(
            "ls-remote",
            self._remote,
            f"refs/heads/{result.source_branch}",
            cwd=workspace,
        )
        pushed_sha = remote_head.split()[0] if remote_head else ""
        if pushed_sha != result.commit_sha:
            raise RuntimeError(
                f"Remote branch points to {pushed_sha}, expected {result.commit_sha}"
            )

        return replace(
            result,
            published=True,
            metadata={
                **dict(result.metadata),
                "published_remote": self._remote,
                "published_repository": task.repository.full_name,
            },
        )
