"""Free-form watchers → agent_jobs adapter.

Webhook / cron / external_signal enqueue agent jobs with an objective.
EVERY watcher-triggered write MUST call catalog_write_authority — no bypass.
"""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.operators import agent_jobs as agent_jobs_mod
from app.services.catalog_write_authority import invoke_action_requires_write_approval
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

VALID_SOURCES = frozenset({"webhook", "cron", "external_signal"})


class WatcherAgentError(Exception):
    def __init__(self, message: str, *, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message)
        self.code = code


def gate_watcher_write(action: str) -> bool:
    """Authority gate for watcher-triggered writes — same SoT as user-initiated paths.

    Returns True when the action requires write approval.
    Always routes through catalog_write_authority.invoke_action_requires_write_approval.
    """
    return invoke_action_requires_write_approval(action)


def assert_watcher_write_allowed(
    action: str | None,
    *,
    approval_granted: bool = False,
) -> dict[str, Any]:
    """Raise if a watcher path attempts a write without approval.

    Read actions pass. Write actions require explicit approval_granted.
    """
    if not action or not str(action).strip():
        return {"requires_write_approval": False, "gated": True, "action": None}
    requires = gate_watcher_write(str(action).strip())
    if requires and not approval_granted:
        raise WatcherAgentError(
            f"Watcher write blocked without approval: {action}. "
            "catalog_write_authority requires human/approval gate (no bypass).",
            code="WRITE_AUTHORITY_DENIED",
        )
    return {
        "requires_write_approval": requires,
        "gated": True,
        "action": str(action).strip(),
        "approval_granted": bool(approval_granted),
    }


class WatcherAgentAdapter:
    """Enqueue agent_jobs from free-form watcher signals."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def enqueue_from_watcher(
        self,
        org_id: str,
        *,
        objective: str,
        source: str,
        agent_id: str | None = None,
        created_by: str | None = None,
        proposed_action: str | None = None,
        approval_granted: bool = False,
        metadata: dict[str, Any] | None = None,
        environment: str = "production",
    ) -> dict[str, Any]:
        clean_objective = (objective or "").strip()
        if not clean_objective:
            raise WatcherAgentError("objective is required", code="VALIDATION_ERROR")
        src = (source or "").strip().lower()
        if src not in VALID_SOURCES:
            raise WatcherAgentError(
                f"source must be one of {sorted(VALID_SOURCES)}",
                code="VALIDATION_ERROR",
            )

        # Gate any proposed write action through catalog_write_authority (no bypass).
        write_gate = assert_watcher_write_allowed(
            proposed_action,
            approval_granted=approval_granted,
        )

        client = self._client()
        payload: dict[str, Any] = {
            "task": clean_objective,
            "objective": clean_objective,
            "source": "watcher",
            "watcherSource": src,
            "agent_id": agent_id,
            "agentId": agent_id,
            "writeAuthorityGated": True,
            "proposedAction": proposed_action,
            "writeGate": write_gate,
            "metadata": metadata or {},
        }
        job = agent_jobs_mod.create_job(
            client,
            org_id,
            kind="watcher_triggered",
            environment=environment,
            payload=payload,
            created_by=created_by,
        )
        job_id = str(job.get("id") or "")
        try:
            from app.workers.queue import enqueue_agent_execution_job

            await enqueue_agent_execution_job(job_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("watcher_agent_enqueue_failed job_id=%s error=%s", job_id, exc)

        return {
            "jobId": job_id,
            "status": job.get("status") or "queued",
            "source": src,
            "objective": clean_objective,
            "writeAuthorityGated": True,
            "writeGate": write_gate,
            "advisoryNote": (
                "Watcher-triggered agent jobs use the same catalog_write_authority "
                "gate as user-initiated writes; no write bypass."
            ),
        }


_adapter: WatcherAgentAdapter | None = None


def get_watcher_agent_adapter(settings: Settings | None = None) -> WatcherAgentAdapter:
    global _adapter
    if _adapter is None or settings is not None:
        _adapter = WatcherAgentAdapter(settings)
    return _adapter
