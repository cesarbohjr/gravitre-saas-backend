"""Ephemeral job workspace — cloud-computer-lite session state (Tier 2)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class JobWorkspaceService:
    """Persists per-job workspace files and browser hints on agent job payload."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    @staticmethod
    def _workspace_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
        ws = payload.get("workspace")
        if isinstance(ws, dict):
            return ws
        return {
            "workspace_id": str(uuid4()),
            "files": {},
            "browser_state": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    async def ensure_workspace(self, job_id: str, org_id: str) -> dict[str, Any]:
        try:
            resp = (
                self._client()
                .table("agent_jobs")
                .select("payload")
                .eq("id", job_id)
                .eq("org_id", org_id)
                .maybe_single()
                .execute()
            )
            row = resp.data or {}
            payload = dict(row.get("payload") or {})
            workspace = self._workspace_from_payload(payload)
            if "workspace" not in payload:
                payload["workspace"] = workspace
                self._client().table("agent_jobs").update({"payload": payload}).eq("id", job_id).execute()
            return workspace
        except Exception as exc:  # noqa: BLE001
            logger.debug("job_workspace_ensure_skipped job_id=%s error=%s", job_id, exc)
            return self._workspace_from_payload({})

    async def write_file(
        self,
        job_id: str,
        org_id: str,
        path: str,
        content: str,
    ) -> dict[str, Any]:
        workspace = await self.ensure_workspace(job_id, org_id)
        files = dict(workspace.get("files") or {})
        files[path] = content[:200_000]
        workspace["files"] = files
        workspace["updated_at"] = datetime.now(timezone.utc).isoformat()
        try:
            resp = (
                self._client()
                .table("agent_jobs")
                .select("payload")
                .eq("id", job_id)
                .eq("org_id", org_id)
                .maybe_single()
                .execute()
            )
            payload = dict((resp.data or {}).get("payload") or {})
            payload["workspace"] = workspace
            self._client().table("agent_jobs").update({"payload": payload}).eq("id", job_id).execute()
        except Exception as exc:  # noqa: BLE001
            logger.debug("job_workspace_write_skipped job_id=%s error=%s", job_id, exc)
        return workspace

    async def get_workspace(self, job_id: str, org_id: str) -> dict[str, Any]:
        return await self.ensure_workspace(job_id, org_id)


_service: JobWorkspaceService | None = None


def get_job_workspace_service(settings: Settings | None = None) -> JobWorkspaceService:
    global _service
    if _service is None or settings is not None:
        _service = JobWorkspaceService(settings)
    return _service
