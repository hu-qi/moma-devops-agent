"""GitHub Actions implementation of the provider-neutral CI contract."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from devopspilot.contracts.providers import (
    CIArtifactRef,
    CICapability,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
)

from .client import GitHubAPIClient


class GitHubCIProvider:
    provider_id = "github-actions"

    def __init__(self, client: GitHubAPIClient) -> None:
        self._client = client

    async def capabilities(self) -> frozenset[CICapability]:
        return frozenset(CICapability)

    async def get_run(
        self,
        repository: RepositoryRef,
        run_id: str,
    ) -> CIRunRef:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/actions/runs/{run_id}",
        )
        return self._to_run(repository, data)

    async def list_runs(
        self,
        repository: RepositoryRef,
        *,
        commit_sha: str | None = None,
        ref: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> tuple[CIRunRef, ...]:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/actions/runs",
            query={
                "head_sha": commit_sha,
                "branch": ref,
                "status": status,
                "per_page": max(1, min(limit, 100)),
                "page": 1,
            },
        )
        return tuple(
            self._to_run(repository, item)
            for item in data.get("workflow_runs", [])
        )

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        jobs = await self._client.request_json(
            "GET",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/jobs",
            query={"per_page": 100},
        )
        for job in jobs.get("jobs", []):
            job_id = str(job["id"])
            raw = await self._client.request_bytes(
                "GET",
                f"/repos/{run.repository.full_name}/actions/jobs/{job_id}/logs",
            )
            yield CIJobLog(
                run=run,
                job_id=job_id,
                job_name=job.get("name", job_id),
                content=raw.decode("utf-8", errors="replace"),
            )

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        await self._client.request_json(
            "POST",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/rerun-failed-jobs",
        )
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=run.run_id,
            repository=run.repository,
            status="queued",
            commit_sha=run.commit_sha,
            web_url=run.web_url,
        )

    async def trigger(
        self,
        repository: RepositoryRef,
        *,
        ref: str,
        workflow_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> CIRunRef:
        if not workflow_id:
            raise ValueError("GitHub Actions trigger requires workflow_id")
        await self._client.request_json(
            "POST",
            f"/repos/{repository.full_name}/actions/workflows/{workflow_id}/dispatches",
            body={"ref": ref, "inputs": dict(inputs or {})},
        )
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=f"dispatch:{workflow_id}:{ref}",
            repository=repository,
            status="queued",
        )

    async def cancel(self, run: CIRunRef) -> None:
        await self._client.request_json(
            "POST",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/cancel",
        )

    async def list_artifacts(self, run: CIRunRef) -> tuple[CIArtifactRef, ...]:
        data = await self._client.request_json(
            "GET",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/artifacts",
            query={"per_page": 100},
        )
        return tuple(
            CIArtifactRef(
                run=run,
                artifact_id=str(item["id"]),
                name=item["name"],
                download_url=item.get("archive_download_url"),
            )
            for item in data.get("artifacts", [])
        )

    def _to_run(
        self,
        repository: RepositoryRef,
        data: Mapping[str, Any],
    ) -> CIRunRef:
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=str(data["id"]),
            repository=repository,
            status=data.get("status", "unknown"),
            conclusion=data.get("conclusion"),
            commit_sha=data.get("head_sha"),
            web_url=data.get("html_url"),
        )
