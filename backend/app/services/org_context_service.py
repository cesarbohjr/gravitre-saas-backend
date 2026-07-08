"""OrgContextService (STA-147 / AI-015) — live org state for AI prompts."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.connectors.repository import list_connectors
from app.core.logging import get_logger
from app.services.workflow_failure_prediction_service import list_failure_alerts
from app.workflows.repository import list_workflows

logger = get_logger(__name__)

OrgContextDepth = Literal["minimal", "standard", "full"]

_CACHE_TTL_SECONDS = 60
from app.connectors.constants import is_connector_usable

_DEPTH_LIMITS: dict[OrgContextDepth, dict[str, int]] = {
    "minimal": {"agents": 0, "workflows": 0, "integrations": 5, "runs": 0, "alerts": 0},
    "standard": {"agents": 8, "workflows": 8, "integrations": 12, "runs": 5, "alerts": 5},
    "full": {"agents": 20, "workflows": 20, "integrations": 30, "runs": 10, "alerts": 10},
}


def _normalize_depth(depth: OrgContextDepth | int | str | None) -> OrgContextDepth:
    if depth is None:
        return "standard"
    if isinstance(depth, int):
        if depth <= 0:
            return "minimal"
        if depth == 1:
            return "standard"
        return "full"
    normalized = str(depth).strip().lower()
    if normalized in _DEPTH_LIMITS:
        return normalized  # type: ignore[return-value]
    return "standard"


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return (
        "does not exist" in message
        or "relation" in message and "does not exist" in message
        or "undefined_table" in message
    )


def _safe_query(loader: Any, default: Any) -> Any:
    try:
        return loader()
    except Exception as exc:  # noqa: BLE001
        if _is_missing_table_error(exc):
            logger.debug("org_context_query_skipped error=%s", exc)
            return default
        logger.warning("org_context_query_failed error=%s", exc)
        return default


@dataclass
class _CacheEntry:
    snapshot: dict[str, Any]
    markdown: str
    expires_at: float


class OrgContextService:
    """Build org-scoped context snapshots for assistant and agent prompts."""

    def __init__(self, *, cache_ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl_seconds = cache_ttl_seconds

    def invalidate(self, org_id: str, *, environment_name: str = "production") -> None:
        prefix = f"{org_id}:{environment_name}:"
        for key in list(self._cache):
            if key.startswith(prefix):
                del self._cache[key]

    def get_snapshot(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str = "production",
        depth: OrgContextDepth | int | str | None = "standard",
        user_id: str | None = None,
    ) -> dict[str, Any]:
        snapshot, _ = self._load(client, org_id, environment_name, depth, user_id)
        return snapshot

    def build_context(
        self,
        client: Any,
        org_id: str,
        user_id: str | None = None,
        depth: OrgContextDepth | int | str | None = "standard",
        *,
        environment_name: str = "production",
    ) -> str:
        _, markdown = self._load(client, org_id, environment_name, depth, user_id)
        return markdown

    def get_context_bundle(
        self,
        client: Any,
        org_id: str,
        *,
        user_id: str | None = None,
        depth: OrgContextDepth | int | str | None = "standard",
        environment_name: str = "production",
    ) -> tuple[dict[str, Any], str]:
        return self._load(client, org_id, environment_name, depth, user_id)

    def _cache_key(self, org_id: str, environment_name: str, depth: OrgContextDepth) -> str:
        return f"{org_id}:{environment_name}:{depth}"

    def _load(
        self,
        client: Any,
        org_id: str,
        environment_name: str,
        depth: OrgContextDepth | int | str | None,
        user_id: str | None,
    ) -> tuple[dict[str, Any], str]:
        normalized_depth = _normalize_depth(depth)
        cache_key = self._cache_key(org_id, environment_name, normalized_depth)
        now = time.monotonic()
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > now:
            return cached.snapshot, cached.markdown

        snapshot = self._fetch_snapshot(
            client,
            org_id,
            environment_name=environment_name,
            depth=normalized_depth,
            user_id=user_id,
        )
        markdown = self._format_markdown(snapshot, normalized_depth)
        self._cache[cache_key] = _CacheEntry(
            snapshot=snapshot,
            markdown=markdown,
            expires_at=now + self._cache_ttl_seconds,
        )
        return snapshot, markdown

    def _fetch_snapshot(
        self,
        client: Any,
        org_id: str,
        *,
        environment_name: str,
        depth: OrgContextDepth,
        user_id: str | None,
    ) -> dict[str, Any]:
        limits = _DEPTH_LIMITS[depth]

        def load_org_name() -> str | None:
            org_row = _safe_query(
                lambda: client.table("organizations")
                .select("id,name")
                .eq("id", org_id)
                .limit(1)
                .execute(),
                None,
            )
            if org_row and getattr(org_row, "data", None):
                return org_row.data[0].get("name")
            return None

        def load_integrations() -> tuple[list[dict[str, Any]], list[str]]:
            from app.config import get_settings
            from app.connectors.connector_availability_service import list_connector_availability

            integrations: list[dict[str, Any]] = []
            availability_rows = list_connector_availability(
                client,
                org_id,
                get_settings(),
                environment_name=environment_name,
                force_live=True,
            )
            for item in availability_rows:
                ctype = str(item.get("vendor") or "").strip()
                if limits["integrations"] and len(integrations) < limits["integrations"]:
                    integrations.append(
                        {
                            "id": str(item.get("connector_id") or ""),
                            "type": ctype or "custom",
                            "status": str(item.get("display_status") or item.get("health_status") or "unknown"),
                            "executionAvailable": bool(item.get("execution_available")),
                        }
                    )
            connected_types = [
                str(item.get("vendor") or "").strip().lower()
                for item in availability_rows
                if item.get("execution_available") and item.get("vendor")
            ]
            return integrations, connected_types

        def load_agents() -> list[dict[str, Any]]:
            agents: list[dict[str, Any]] = []
            if not limits["agents"]:
                return agents
            agent_rows = _safe_query(
                lambda: client.table("agents")
                .select("id,name,status,role")
                .eq("org_id", org_id)
                .order("updated_at", desc=True)
                .limit(limits["agents"])
                .execute(),
                None,
            )
            for row in list(getattr(agent_rows, "data", None) or []):
                agents.append(
                    {
                        "id": str(row.get("id") or ""),
                        "name": str(row.get("name") or "Agent"),
                        "status": str(row.get("status") or "idle"),
                        "role": str(row.get("role") or ""),
                    }
                )
            return agents

        def load_workflows() -> list[dict[str, Any]]:
            workflows: list[dict[str, Any]] = []
            if not limits["workflows"]:
                return workflows
            for row in list_workflows(client, org_id)[: limits["workflows"]]:
                workflows.append(
                    {
                        "id": str(row.get("id") or ""),
                        "name": str(row.get("name") or "Workflow"),
                        "status": str(row.get("status") or "draft"),
                        "successRate": row.get("success_rate"),
                        "lastRunAt": row.get("last_run_at"),
                    }
                )
            return workflows

        def load_runs() -> list[dict[str, Any]]:
            recent_runs: list[dict[str, Any]] = []
            if not limits["runs"]:
                return recent_runs
            run_rows = _safe_query(
                lambda: client.table("workflow_runs")
                .select("id,status,created_at,workflow_id,run_type")
                .eq("org_id", org_id)
                .eq("environment", environment_name)
                .order("created_at", desc=True)
                .limit(limits["runs"])
                .execute(),
                None,
            )
            for row in list(getattr(run_rows, "data", None) or []):
                recent_runs.append(
                    {
                        "id": str(row.get("id") or ""),
                        "status": str(row.get("status") or ""),
                        "runType": str(row.get("run_type") or "execute"),
                        "workflowId": str(row.get("workflow_id") or ""),
                        "createdAt": row.get("created_at"),
                    }
                )
            return recent_runs

        def load_alerts() -> list[dict[str, Any]]:
            if not limits["alerts"]:
                return []
            return list_failure_alerts(client, org_id, status="open", limit=limits["alerts"])

        org_name: str | None = None
        integrations: list[dict[str, Any]] = []
        connected_types: list[str] = []
        agents: list[dict[str, Any]] = []
        workflows: list[dict[str, Any]] = []
        recent_runs: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {
                pool.submit(load_org_name): "org_name",
                pool.submit(load_integrations): "integrations",
                pool.submit(load_agents): "agents",
                pool.submit(load_workflows): "workflows",
                pool.submit(load_runs): "runs",
                pool.submit(load_alerts): "alerts",
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("org_context_parallel_fetch_failed key=%s error=%s", key, exc)
                    continue
                if key == "org_name":
                    org_name = result
                elif key == "integrations":
                    integrations, connected_types = result
                elif key == "agents":
                    agents = result
                elif key == "workflows":
                    workflows = result
                elif key == "runs":
                    recent_runs = result
                elif key == "alerts":
                    alerts = result

        generated_at = datetime.now(timezone.utc).isoformat()
        snapshot: dict[str, Any] = {
            "orgId": org_id,
            "orgName": org_name,
            "environment": environment_name,
            "generatedAt": generated_at,
            "depth": depth,
            "connectedIntegrations": sorted(set(connected_types)),
            "connectorCount": len(connected_types),
            "integrations": integrations,
            "agents": agents,
            "workflows": workflows,
            "recentRuns": recent_runs,
            "alerts": alerts,
            "counts": {
                "agents": len(agents),
                "workflows": len(workflows),
                "integrations": len(integrations),
                "connectedIntegrations": len(connected_types),
                "recentRuns": len(recent_runs),
                "openAlerts": len(alerts),
            },
        }
        if user_id:
            snapshot["userId"] = user_id
        return snapshot

    @staticmethod
    def _format_markdown(snapshot: dict[str, Any], depth: OrgContextDepth) -> str:
        lines = ["## Organization context (live snapshot)"]
        org_name = snapshot.get("orgName") or snapshot.get("orgId")
        lines.append(f"- Organization: {org_name}")
        lines.append(f"- Environment: {snapshot.get('environment') or 'default'}")
        lines.append(f"- Generated: {snapshot.get('generatedAt') or 'unknown'}")

        connected = snapshot.get("connectedIntegrations") or []
        if connected:
            lines.append(f"- Active integrations: {', '.join(connected)}")
        else:
            lines.append("- Active integrations: none")

        counts = snapshot.get("counts") or {}
        if depth != "minimal":
            agents = snapshot.get("agents") or []
            if agents:
                lines.append("")
                lines.append("### Agents")
                for agent in agents:
                    role = agent.get("role")
                    role_suffix = f" ({role})" if role else ""
                    lines.append(
                        f"- {agent.get('name')}{role_suffix}: {agent.get('status') or 'idle'}"
                    )
            elif counts.get("agents") == 0:
                lines.append("")
                lines.append("### Agents")
                lines.append("- No agents configured")

            workflows = snapshot.get("workflows") or []
            if workflows:
                lines.append("")
                lines.append("### Workflows")
                for wf in workflows:
                    status = wf.get("status") or "draft"
                    lines.append(f"- {wf.get('name')}: {status}")
            elif counts.get("workflows") == 0:
                lines.append("")
                lines.append("### Workflows")
                lines.append("- No workflows configured")

            runs = snapshot.get("recentRuns") or []
            if runs:
                lines.append("")
                lines.append("### Recent workflow runs")
                for run in runs:
                    lines.append(
                        f"- {run.get('runType') or 'execute'} run {run.get('status') or 'unknown'}"
                        f" ({run.get('createdAt') or 'recent'})"
                    )

            alerts = snapshot.get("alerts") or []
            if alerts:
                lines.append("")
                lines.append("### Active alerts")
                for alert in alerts:
                    severity = alert.get("severity") or "info"
                    title = alert.get("title") or alert.get("alert_type") or "Alert"
                    lines.append(f"- [{severity}] {title}")

        return "\n".join(lines)


_org_context_service_singleton: OrgContextService | None = None


def get_org_context_service() -> OrgContextService:
    global _org_context_service_singleton
    if _org_context_service_singleton is None:
        _org_context_service_singleton = OrgContextService()
    return _org_context_service_singleton
