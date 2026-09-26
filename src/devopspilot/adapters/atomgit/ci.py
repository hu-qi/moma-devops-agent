"""AtomGit implementation of the provider-neutral CI contract."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Mapping

from devopspilot.contracts.providers import (
    CIArtifactRef,
    CICapability,
    CIJobLog,
    CIRunRef,
    RepositoryRef,
)
from .client import AtomGitAPIClient


class AtomGitCIProvider:
    provider_id = "atomgit-ci"

    def __init__(self, client: AtomGitAPIClient) -> None:
        self._client = client

    async def capabilities(self) -> frozenset[CICapability]:
        return frozenset({
            CICapability.RUNS,
            CICapability.JOBS,
            CICapability.LOGS,
            CICapability.TRIGGER,
            CICapability.CANCEL,
            CICapability.RETRY,
        })

    async def get_run(
        self,
        repository: RepositoryRef,
        run_id: str,
    ) -> CIRunRef:
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/actions/runs/{run_id}",
        )
        return self._map_run(repository, data)

    async def list_runs(
        self,
        repository: RepositoryRef,
        *,
        commit_sha: str | None = None,
        branch: str | None = None,
        status: str | None = None,
        limit: int = 20,
    ) -> tuple[CIRunRef, ...]:
        query: dict[str, Any] = {"per_page": limit}
        if commit_sha:
            query["head_sha"] = commit_sha
        if branch:
            query["branch"] = branch
        if status:
            query["status"] = status
        data = await self._client.request_json(
            "GET",
            f"/repos/{repository.full_name}/actions/runs",
            query=query,
        )
        runs = data.get("workflow_runs", []) if isinstance(data, dict) else (data or [])
        return tuple(self._map_run(repository, item) for item in runs)

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        data = await self._client.request_json(
            "GET",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/jobs",
            query={"per_page": 100},
        )
        jobs = data.get("jobs", []) if isinstance(data, dict) else (data or [])
        for job in jobs:
            job_id = str(job["id"])
            job_name = str(job.get("name", job_id))
            try:
                raw = await self._client.request_bytes(
                    "GET",
                    f"/repos/{run.repository.full_name}/actions/jobs/{job_id}/logs",
                )
                content = raw.decode("utf-8", errors="replace")
            except Exception:
                content = f"Log unavailable for job {job_id}"
            yield CIJobLog(
                run=run,
                job_id=job_id,
                job_name=job_name,
                content=content,
            )

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        data = await self._client.request_json(
            "POST",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/rerun-failed-jobs",
        )
        return self._map_run(run.repository, data or {"id": run.run_id, "status": "queued"})

    async def trigger(
        self,
        repository: RepositoryRef,
        *,
        ref: str,
        workflow_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> CIRunRef:
        target_wf = workflow_id or "ci.yml"
        data = await self._client.request_json(
            "POST",
            f"/repos/{repository.full_name}/actions/workflows/{target_wf}/dispatches",
            body={"ref": ref, "inputs": dict(inputs or {})},
        )
        return self._map_run(repository, data or {"id": "pending", "status": "queued"})

    async def cancel(
        self,
        run: CIRunRef,
    ) -> None:
        await self._client.request_json(
            "POST",
            f"/repos/{run.repository.full_name}/actions/runs/{run.run_id}/cancel",
        )

    # Compatibility aliases
    async def trigger_workflow(
        self,
        repository: RepositoryRef,
        workflow_id: str,
        *,
        ref: str,
        inputs: Mapping[str, Any] | None = None,
    ) -> None:
        await self.trigger(repository, ref=ref, workflow_id=workflow_id, inputs=inputs)

    async def cancel_run(
        self,
        repository: RepositoryRef,
        run_id: str,
    ) -> None:
        run = CIRunRef(
            provider_id=self.provider_id,
            run_id=run_id,
            repository=repository,
            status="unknown",
        )
        await self.cancel(run)

    async def rerun_failed(
        self,
        repository: RepositoryRef,
        run_id: str,
    ) -> None:
        run = CIRunRef(
            provider_id=self.provider_id,
            run_id=run_id,
            repository=repository,
            status="unknown",
        )
        await self.retry_failed(run)

    def _map_run(
        self,
        repository: RepositoryRef,
        data: Mapping[str, Any],
    ) -> CIRunRef:
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=str(data["id"]),
            repository=repository,
            status=str(data.get("status", "unknown")),
            conclusion=data.get("conclusion"),
            web_url=data.get("html_url"),
        )
