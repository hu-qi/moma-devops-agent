"""CNB cloud-native build mapping to DevOpsPilot CIProvider."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from devopspilot.contracts.providers import (
    CIArtifactRef, CICapability, CIJobLog, CIRunRef, RepositoryRef,
)
from .client import CNBAPIClient, CNBHTTPClient


_SUCCESS = {"success"}
_FAILURE = {"error", "failed", "failure"}
_TERMINAL = _SUCCESS | _FAILURE | {"cancel", "cancelled", "canceled", "skipped"}


class CNBCIProvider:
    provider_id = "cnb-build"

    def __init__(self, client: CNBAPIClient) -> None:
        self._client = client

    async def capabilities(self) -> frozenset[CICapability]:
        # CNB exposes start/status/stop and stage logs. No dedicated retry API
        # is present in the current Swagger, so RETRY is intentionally omitted.
        return frozenset({
            CICapability.RUNS, CICapability.JOBS, CICapability.LOGS,
            CICapability.TRIGGER, CICapability.CANCEL,
        })

    async def get_run(self, repository: RepositoryRef, run_id: str) -> CIRunRef:
        data = await self._status(repository, run_id)
        status = str(data.get("status", "unknown"))
        conclusion = self._conclusion(status)
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=run_id,
            repository=repository,
            status="completed" if status.lower() in _TERMINAL else status,
            conclusion=conclusion,
            web_url=f"https://cnb.cool/{repository.full_name}/-/build/{run_id}",
        )

    async def stream_logs(self, run: CIRunRef) -> AsyncIterator[CIJobLog]:
        status = await self._status(run.repository, run.run_id)
        pipelines = status.get("pipelinesStatus") or {}
        for key, pipeline in pipelines.items():
            if not isinstance(pipeline, dict):
                continue
            pipeline_id = str(pipeline.get("id") or key)
            for stage in pipeline.get("stages") or []:
                if not isinstance(stage, dict) or not stage.get("id"):
                    continue
                stage_id = str(stage["id"])
                detail = await self._client.request_json(
                    "GET",
                    f"/{CNBHTTPClient.repo_path(run.repository.full_name)}"
                    f"/-/build/logs/stage/{run.run_id}/{pipeline_id}/{stage_id}",
                )
                content = "\n".join(str(line) for line in (detail.get("content") or []))
                if detail.get("error"):
                    content = (content + "\n" + str(detail["error"])).strip()
                yield CIJobLog(
                    run=run,
                    job_id=f"{pipeline_id}:{stage_id}",
                    job_name=str(detail.get("name") or stage.get("name") or stage_id),
                    content=content,
                )

    async def retry_failed(self, run: CIRunRef) -> CIRunRef:
        raise NotImplementedError("CNB current OpenAPI has no dedicated retry/rerun operation")

    async def trigger(
        self, repository: RepositoryRef, *, ref: str,
        workflow_id: str | None = None,
        inputs: Mapping[str, Any] | None = None,
    ) -> CIRunRef:
        body: dict[str, Any] = {
            "branch": ref,
            "event": "api_trigger",
            "sync": "false",
        }
        if inputs:
            body["env"] = {str(k): str(v) for k, v in inputs.items()}
        data = await self._client.request_json(
            "POST",
            f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/build/start",
            body=body,
        )
        return CIRunRef(
            provider_id=self.provider_id,
            run_id=str(data["sn"]),
            repository=repository,
            status="queued" if data.get("success", True) else "error",
            web_url=data.get("buildLogUrl"),
        )

    async def cancel(self, run: CIRunRef) -> None:
        await self._client.request_json(
            "POST",
            f"/{CNBHTTPClient.repo_path(run.repository.full_name)}/-/build/stop/{run.run_id}",
        )

    async def list_artifacts(self, run: CIRunRef) -> tuple[CIArtifactRef, ...]:
        # Artifact APIs exist elsewhere in CNB, but build-to-artifact correlation
        # has not yet been verified; do not fabricate that mapping.
        return ()

    async def _status(self, repository: RepositoryRef, run_id: str) -> Mapping[str, Any]:
        data = await self._client.request_json(
            "GET",
            f"/{CNBHTTPClient.repo_path(repository.full_name)}/-/build/status/{run_id}",
        )
        return data or {}

    @staticmethod
    def _conclusion(status: str) -> str | None:
        s = status.lower()
        if s in _SUCCESS:
            return "success"
        if s in _FAILURE:
            return "failure"
        if s in {"cancel", "cancelled", "canceled"}:
            return "cancelled"
        if s == "skipped":
            return "skipped"
        return None
