"""v8 Outcome-Linked Learning — correlational attribution, not reinforcement learning."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.connectors.hubspot import HubSpotAPIError, get_deal
from app.connectors.hubspot_oauth import ensure_hubspot_access_token
from app.connectors.repository import get_connector, get_connector_by_type
from app.core.logging import get_logger
from app.services.tool_types import ToolContext
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

CONFIDENCE_NOTE = (
    "correlational only; other factors may have contributed to this metric change"
)
MIN_SAMPLE_SIZE = 15
DEFAULT_ATTRIBUTION_WINDOW_DAYS = 14

ENTITY_DEAL = "deal"
METRIC_DEAL_AMOUNT = "deal_amount"

HUBSPOT_DEAL_ACTIONS = frozenset(
    {"hubspot.deals.update", "hubspot.deals.update_stage"}
)


def _parse_deal_amount(deal_payload: dict[str, Any]) -> float | None:
    props = deal_payload.get("properties") or {}
    raw = props.get("amount")
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _hubspot_token_for_org(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
) -> str | None:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name="default")
    if not conn:
        conn = get_connector_by_type(client, org_id, "hubspot", environment_name="default")
    if not conn:
        return None
    cid = str(conn["id"])
    token, err = ensure_hubspot_access_token(
        client,
        org_id,
        cid,
        settings,
        environment_name=str(conn.get("environment") or "default"),
    )
    if err or not token:
        return None
    return token


class OutcomeAttributionService:
    """Two-phase outcome capture: baseline at action time, measurement after attribution window."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    async def record_action_baseline(
        self,
        org_id: str,
        *,
        agent_id: str | None,
        workflow_run_id: str | None,
        target_entity_type: str,
        target_entity_id: str,
        action_type: str,
        metric_name: str,
        metric_value_before: float | None,
        attribution_window_days: int = DEFAULT_ATTRIBUTION_WINDOW_DAYS,
    ) -> dict[str, Any] | None:
        if metric_value_before is None:
            return None
        client = self._client()
        payload = {
            "org_id": org_id,
            "agent_id": agent_id,
            "workflow_run_id": workflow_run_id,
            "action_type": action_type,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
            "action_taken_at": self._now().isoformat(),
            "metric_name": metric_name,
            "metric_value_before": float(metric_value_before),
            "metric_value_after": None,
            "attribution_window_days": int(attribution_window_days),
            "measured_at": None,
            "confidence_note": CONFIDENCE_NOTE,
        }
        inserted = client.table("agent_action_outcomes").insert(payload).execute()
        return inserted.data[0] if inserted.data else payload

    async def measure_outcomes_due(self, org_id: str) -> int:
        """Scheduled job: populate metric_value_after after attribution window elapses."""
        client = self._client()
        now = self._now()
        rows = (
            client.table("agent_action_outcomes")
            .select("*")
            .eq("org_id", org_id)
            .is_("measured_at", "null")
            .limit(500)
            .execute()
            .data
            or []
        )
        measured = 0
        for row in rows:
            action_at_raw = row.get("action_taken_at")
            if not action_at_raw:
                continue
            action_at = datetime.fromisoformat(str(action_at_raw).replace("Z", "+00:00"))
            window_days = int(row.get("attribution_window_days") or DEFAULT_ATTRIBUTION_WINDOW_DAYS)
            if action_at + timedelta(days=window_days) > now:
                continue
            after_value = await self._fetch_current_metric_value(
                org_id,
                target_entity_type=str(row.get("target_entity_type") or ""),
                target_entity_id=str(row.get("target_entity_id") or ""),
                metric_name=str(row.get("metric_name") or ""),
            )
            if after_value is None:
                continue
            client.table("agent_action_outcomes").update(
                {
                    "metric_value_after": float(after_value),
                    "measured_at": now.isoformat(),
                    "confidence_note": CONFIDENCE_NOTE,
                }
            ).eq("id", row["id"]).execute()
            measured += 1
        return measured

    async def _fetch_current_metric_value(
        self,
        org_id: str,
        *,
        target_entity_type: str,
        target_entity_id: str,
        metric_name: str,
    ) -> float | None:
        if target_entity_type == ENTITY_DEAL and metric_name == METRIC_DEAL_AMOUNT:
            client = self._client()
            token = _hubspot_token_for_org(client, org_id, None, self.settings)
            if not token:
                return None
            try:
                deal = get_deal(token, target_entity_id, properties=["amount"])
            except HubSpotAPIError as exc:
                logger.warning(
                    "outcome_metric_fetch_failed org=%s deal=%s error=%s",
                    org_id,
                    target_entity_id,
                    exc,
                )
                return None
            return _parse_deal_amount(deal)
        return None

    async def get_agent_outcome_summary(self, org_id: str, agent_id: str) -> dict[str, Any]:
        client = self._client()
        rows = (
            client.table("agent_action_outcomes")
            .select("*")
            .eq("org_id", org_id)
            .eq("agent_id", agent_id)
            .not_.is_("measured_at", "null")
            .execute()
            .data
            or []
        )
        deltas: list[float] = []
        wins = 0
        for row in rows:
            before = row.get("metric_value_before")
            after = row.get("metric_value_after")
            if before is None or after is None:
                continue
            try:
                delta = float(after) - float(before)
            except (TypeError, ValueError):
                continue
            deltas.append(delta)
            if delta > 0:
                wins += 1
        sample_size = len(deltas)
        sufficient = sample_size >= MIN_SAMPLE_SIZE
        summary: dict[str, Any] = {
            "agentId": agent_id,
            "sampleSize": sample_size,
            "minSampleSize": MIN_SAMPLE_SIZE,
            "sufficientData": sufficient,
            "confidenceNote": CONFIDENCE_NOTE,
        }
        if not sufficient:
            summary["message"] = "insufficient data to draw a conclusion"
            summary["winRate"] = None
            summary["avgMetricDelta"] = None
            return summary
        summary["winRate"] = wins / sample_size if sample_size else 0.0
        summary["avgMetricDelta"] = sum(deltas) / sample_size if sample_size else 0.0
        return summary

    async def load_admin_outcomes_snapshot(
        self,
        org_id: str,
        *,
        settings: Settings | None = None,
    ) -> dict[str, Any]:
        active_settings = settings or self.settings
        client = get_supabase_client(active_settings)
        agents = (
            client.table("agents")
            .select("id, name, status")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        summaries: list[dict[str, Any]] = []
        for agent in agents:
            agent_id = str(agent.get("id") or "")
            if not agent_id:
                continue
            summary = await self.get_agent_outcome_summary(org_id, agent_id)
            summary["agentName"] = str(agent.get("name") or agent_id)
            summaries.append(summary)
        pending = (
            client.table("agent_action_outcomes")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .is_("measured_at", "null")
            .execute()
        )
        return {
            "scopeNote": (
                "Outcome summaries link agent actions to observable connector metrics "
                "(HubSpot deal amount today). Correlational only — not causal inference or RL."
            ),
            "observableMetrics": [
                {"connector": "hubspot", "entityType": ENTITY_DEAL, "metric": METRIC_DEAL_AMOUNT}
            ],
            "confidenceNote": CONFIDENCE_NOTE,
            "minSampleSize": MIN_SAMPLE_SIZE,
            "agentSummaries": summaries,
            "pendingMeasurements": int(pending.count or 0),
        }


def maybe_record_hubspot_deal_outcome_baseline(
    ctx: ToolContext,
    *,
    deal_id: str,
    action_type: str,
    token: str,
) -> None:
    """Sync hook from invoke_tool after HubSpot deal mutations."""
    if action_type not in HUBSPOT_DEAL_ACTIONS:
        return
    try:
        deal = get_deal(token, str(deal_id), properties=["amount"])
        amount = _parse_deal_amount(deal)
        if amount is None:
            return
        service = OutcomeAttributionService(settings=ctx.settings)
        client = service._client()
        payload = {
            "org_id": ctx.org_id,
            "agent_id": ctx.agent_id,
            "workflow_run_id": ctx.run_id,
            "action_type": action_type,
            "target_entity_type": ENTITY_DEAL,
            "target_entity_id": str(deal_id),
            "action_taken_at": datetime.now(timezone.utc).isoformat(),
            "metric_name": METRIC_DEAL_AMOUNT,
            "metric_value_before": float(amount),
            "metric_value_after": None,
            "attribution_window_days": DEFAULT_ATTRIBUTION_WINDOW_DAYS,
            "measured_at": None,
            "confidence_note": CONFIDENCE_NOTE,
        }
        client.table("agent_action_outcomes").insert(payload).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outcome_baseline_record_failed org=%s deal=%s action=%s error=%s",
            ctx.org_id,
            deal_id,
            action_type,
            exc,
        )


_outcome_attribution_service: OutcomeAttributionService | None = None


def get_outcome_attribution_service(settings: Settings | None = None) -> OutcomeAttributionService:
    global _outcome_attribution_service
    if settings is not None:
        return OutcomeAttributionService(settings=settings)
    if _outcome_attribution_service is None:
        _outcome_attribution_service = OutcomeAttributionService()
    return _outcome_attribution_service
