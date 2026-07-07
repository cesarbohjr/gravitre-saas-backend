"""Post-publish marketing metrics → outcome attribution + optimization suggestions (STA-293 Mode A)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.outcome_attribution_service import CONFIDENCE_NOTE, get_attribution_window
from app.services.tool_types import NormalizedResult, ToolContext
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

ENTITY_MARKETING_CAMPAIGN = "marketing_campaign"
ENTITY_LINKEDIN_POST = "linkedin_post"
ENTITY_CANVA_EXPORT = "canva_export"
ENTITY_HUBSPOT_CAMPAIGN = "hubspot_campaign"

METRIC_GA4_SESSIONS = "ga4_sessions"
METRIC_GA4_CONVERSIONS = "ga4_conversions"
METRIC_LINKEDIN_ENGAGEMENT = "linkedin_engagement"
METRIC_CANVA_EXPORT_COMPLETED = "canva_export_completed"
METRIC_HUBSPOT_CAMPAIGN_CONTACTS = "hubspot_campaign_contacts"

MARKETING_ENTITY_TYPES = frozenset(
    {
        ENTITY_MARKETING_CAMPAIGN,
        ENTITY_LINKEDIN_POST,
        ENTITY_CANVA_EXPORT,
        ENTITY_HUBSPOT_CAMPAIGN,
    }
)

MARKETING_PUBLISH_ACTIONS = frozenset(
    {
        "analytics.reports.run",
        "canva.exports.create",
        "canva.batch.exports",
        "linkedin.posts.publish",
        "linkedin.posts.create",
        "linkedin.ugcPosts.create",
    }
)

MARKETING_ATTRIBUTION_WINDOWS: dict[str, int] = {
    "analytics.reports.run": 14,
    "canva.exports.create": 7,
    "canva.batch.exports": 7,
    "linkedin.posts.publish": 7,
    "linkedin.posts.create": 7,
    "linkedin.ugcPosts.create": 7,
}

OBSERVABLE_MARKETING_METRICS: list[dict[str, str]] = [
    {"connector": "google_analytics", "entityType": ENTITY_MARKETING_CAMPAIGN, "metric": METRIC_GA4_SESSIONS},
    {"connector": "google_analytics", "entityType": ENTITY_MARKETING_CAMPAIGN, "metric": METRIC_GA4_CONVERSIONS},
    {"connector": "linkedin", "entityType": ENTITY_LINKEDIN_POST, "metric": METRIC_LINKEDIN_ENGAGEMENT},
    {"connector": "canva", "entityType": ENTITY_CANVA_EXPORT, "metric": METRIC_CANVA_EXPORT_COMPLETED},
    {
        "connector": "hubspot_campaign",
        "entityType": ENTITY_HUBSPOT_CAMPAIGN,
        "metric": METRIC_HUBSPOT_CAMPAIGN_CONTACTS,
    },
]

MIN_MARKETING_SUGGESTION_SAMPLES = 5
MARKETING_UNDERPERFORMANCE_DELTA_RATIO = -0.15


def marketing_attribution_window(action_type: str) -> int:
    return MARKETING_ATTRIBUTION_WINDOWS.get(action_type, get_attribution_window(action_type))


def encode_ga4_entity_id(property_id: str, campaign_name: str) -> str:
    return f"{property_id}::{campaign_name}"


def decode_ga4_entity_id(entity_id: str) -> tuple[str, str]:
    if "::" in entity_id:
        property_id, campaign = entity_id.split("::", 1)
        return property_id, campaign
    return "", entity_id


def _dimension_value_at(dimension_values: list[Any], index: int) -> str:
    if index >= len(dimension_values):
        return "(not set)"
    raw = dimension_values[index]
    if isinstance(raw, dict):
        return str(raw.get("value") or "(not set)")
    return str(raw or "(not set)")


def _ga4_report_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in report.get("rows") or []:
        if not isinstance(row, dict):
            continue
        dims = row.get("dimensionValues") or []
        mets = row.get("metricValues") or []
        campaign = _dimension_value_at(dims, 0)
        sessions = _metric_value_at(mets, 0)
        conversions = _metric_value_at(mets, 1)
        rows.append(
            {
                "campaign": campaign,
                "sessions": sessions,
                "conversions": conversions,
            }
        )
    return rows


def _metric_value_at(metric_values: list[Any], index: int) -> float:
    if index >= len(metric_values):
        return 0.0
    raw = metric_values[index]
    if isinstance(raw, dict):
        raw = raw.get("value")
    try:
        return float(raw or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _insert_outcome_row(
    client: Any,
    *,
    org_id: str,
    agent_id: str | None,
    workflow_run_id: str | None,
    action_type: str,
    target_entity_type: str,
    target_entity_id: str,
    metric_name: str,
    metric_value_before: float,
) -> None:
    payload = {
        "org_id": org_id,
        "agent_id": agent_id,
        "workflow_run_id": workflow_run_id,
        "action_type": action_type,
        "target_entity_type": target_entity_type,
        "target_entity_id": target_entity_id,
        "action_taken_at": datetime.now(timezone.utc).isoformat(),
        "metric_name": metric_name,
        "metric_value_before": float(metric_value_before),
        "metric_value_after": None,
        "attribution_window_days": marketing_attribution_window(action_type),
        "measured_at": None,
        "confidence_note": CONFIDENCE_NOTE,
    }
    client.table("agent_action_outcomes").insert(payload).execute()


def _record_ga4_campaign_baselines(
    ctx: ToolContext,
    *,
    action_type: str,
    property_id: str,
    report: dict[str, Any],
) -> None:
    rows = _ga4_report_rows(report)
    if not rows:
        return
    top = max(rows, key=lambda row: row["sessions"])
    entity_id = encode_ga4_entity_id(property_id, str(top["campaign"]))
    client = get_supabase_client(ctx.settings)
    _insert_outcome_row(
        client,
        org_id=ctx.org_id,
        agent_id=ctx.agent_id,
        workflow_run_id=ctx.run_id,
        action_type=action_type,
        target_entity_type=ENTITY_MARKETING_CAMPAIGN,
        target_entity_id=entity_id,
        metric_name=METRIC_GA4_SESSIONS,
        metric_value_before=float(top["sessions"]),
    )
    _insert_outcome_row(
        client,
        org_id=ctx.org_id,
        agent_id=ctx.agent_id,
        workflow_run_id=ctx.run_id,
        action_type=action_type,
        target_entity_type=ENTITY_MARKETING_CAMPAIGN,
        target_entity_id=entity_id,
        metric_name=METRIC_GA4_CONVERSIONS,
        metric_value_before=float(top["conversions"]),
    )
    _insert_outcome_row(
        client,
        org_id=ctx.org_id,
        agent_id=ctx.agent_id,
        workflow_run_id=ctx.run_id,
        action_type=action_type,
        target_entity_type=ENTITY_HUBSPOT_CAMPAIGN,
        target_entity_id=str(top["campaign"]),
        metric_name=METRIC_HUBSPOT_CAMPAIGN_CONTACTS,
        metric_value_before=0.0,
    )


def _record_canva_export_baseline(ctx: ToolContext, *, action_type: str, data: dict[str, Any]) -> None:
    export = data.get("export") if isinstance(data.get("export"), dict) else data
    export_id = str(export.get("id") or export.get("export_id") or data.get("export_id") or "").strip()
    design_id = str(export.get("design_id") or data.get("design_id") or "").strip()
    entity_id = export_id or design_id
    if not entity_id:
        return
    client = get_supabase_client(ctx.settings)
    _insert_outcome_row(
        client,
        org_id=ctx.org_id,
        agent_id=ctx.agent_id,
        workflow_run_id=ctx.run_id,
        action_type=action_type,
        target_entity_type=ENTITY_CANVA_EXPORT,
        target_entity_id=entity_id,
        metric_name=METRIC_CANVA_EXPORT_COMPLETED,
        metric_value_before=0.0,
    )


def _record_linkedin_post_baseline(ctx: ToolContext, *, action_type: str, data: dict[str, Any]) -> None:
    post_id = str(
        data.get("id")
        or data.get("post_id")
        or data.get("postId")
        or (data.get("ugcPost") or {}).get("id")
        or ""
    ).strip()
    if not post_id:
        return
    client = get_supabase_client(ctx.settings)
    _insert_outcome_row(
        client,
        org_id=ctx.org_id,
        agent_id=ctx.agent_id,
        workflow_run_id=ctx.run_id,
        action_type=action_type,
        target_entity_type=ENTITY_LINKEDIN_POST,
        target_entity_id=post_id,
        metric_name=METRIC_LINKEDIN_ENGAGEMENT,
        metric_value_before=0.0,
    )


def maybe_record_post_publish_marketing_baseline(
    ctx: ToolContext,
    *,
    action: str,
    params: dict[str, Any],
    result: NormalizedResult,
) -> None:
    """Sync hook from invoke_tool after marketing publish / snapshot actions."""
    if not result.success or action not in MARKETING_PUBLISH_ACTIONS:
        return
    if not ctx.agent_id:
        return
    try:
        data = result.data or {}
        if action == "analytics.reports.run":
            property_id = str(data.get("property_id") or params.get("property_id") or params.get("propertyId") or "")
            report = data.get("report") or {}
            if property_id and isinstance(report, dict):
                _record_ga4_campaign_baselines(
                    ctx,
                    action_type=action,
                    property_id=property_id,
                    report=report,
                )
        elif action in {"canva.exports.create", "canva.batch.exports"}:
            _record_canva_export_baseline(ctx, action_type=action, data=data if isinstance(data, dict) else {})
        elif action in {"linkedin.posts.publish", "linkedin.posts.create", "linkedin.ugcPosts.create"}:
            _record_linkedin_post_baseline(ctx, action_type=action, data=data if isinstance(data, dict) else {})
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "post_publish_marketing_baseline_failed org=%s action=%s error=%s",
            ctx.org_id,
            action,
            exc,
        )


def _ga4_token_and_property(
    client: Any,
    org_id: str,
    property_id: str,
    settings: Settings,
) -> tuple[str | None, str]:
    from app.connectors.google_analytics_oauth import ensure_google_analytics_session
    from app.connectors.repository import get_connector_by_type

    conn = get_connector_by_type(client, org_id, "google_analytics", environment_name="default")
    if not conn:
        return None, property_id
    if not property_id:
        cfg = conn.get("config") if isinstance(conn.get("config"), dict) else {}
        property_id = str(cfg.get("property_id") or cfg.get("propertyId") or "").strip()
    token, err = ensure_google_analytics_session(
        client,
        org_id,
        str(conn["id"]),
        settings,
        environment_name=str(conn.get("environment") or "default"),
    )
    if err or not token:
        return None, property_id
    return token, property_id


async def fetch_marketing_metric_value(
    org_id: str,
    *,
    target_entity_type: str,
    target_entity_id: str,
    metric_name: str,
    settings: Settings | None = None,
) -> float | None:
    active_settings = settings or get_settings()
    client = get_supabase_client(active_settings)

    if target_entity_type == ENTITY_MARKETING_CAMPAIGN:
        property_id, campaign = decode_ga4_entity_id(target_entity_id)
        token, property_id = _ga4_token_and_property(client, org_id, property_id, active_settings)
        if not token or not property_id:
            return None
        from app.connectors.google_analytics import GoogleAnalyticsAPIError, run_ga4_report

        try:
            report = run_ga4_report(
                token,
                property_id,
                start_date="7daysAgo",
                end_date="today",
                dimensions=["sessionCampaignName"],
                metrics=["sessions", "conversions"],
            )
        except GoogleAnalyticsAPIError as exc:
            logger.warning(
                "marketing_metric_fetch_failed org=%s campaign=%s error=%s",
                org_id,
                campaign,
                exc,
            )
            return None
        for row in _ga4_report_rows(report):
            if str(row["campaign"]) == campaign:
                if metric_name == METRIC_GA4_SESSIONS:
                    return float(row["sessions"])
                if metric_name == METRIC_GA4_CONVERSIONS:
                    return float(row["conversions"])
        return 0.0

    if target_entity_type == ENTITY_CANVA_EXPORT:
        from app.services.canva_tools import fetch_canva_export

        payload = fetch_canva_export(client, org_id, target_entity_id, active_settings)
        if payload is None:
            logger.warning(
                "marketing_metric_fetch_failed org=%s export=%s error=canva_export_unavailable",
                org_id,
                target_entity_id,
            )
            return None
        export = payload.get("export") if isinstance(payload.get("export"), dict) else payload
        status = str(export.get("status") or export.get("state") or "").lower()
        if status in {"success", "completed", "done"}:
            return 1.0
        if status in {"failed", "error"}:
            return 0.0
        return 0.5

    if target_entity_type == ENTITY_LINKEDIN_POST:
        from app.connectors.linkedin import LinkedInAPIError, fetch_linkedin_post_engagement
        from app.connectors.repository import get_connector_by_type

        conn = get_connector_by_type(client, org_id, "linkedin", environment_name="default")
        if not conn:
            return None
        from app.connectors.linkedin import load_linkedin_access_token

        token = load_linkedin_access_token(client, str(conn["id"]), active_settings)
        if not token:
            return None
        try:
            return fetch_linkedin_post_engagement(token, target_entity_id)
        except LinkedInAPIError as exc:
            logger.warning(
                "marketing_metric_fetch_failed org=%s post=%s error=%s",
                org_id,
                target_entity_id,
                exc,
            )
            return None

    if target_entity_type == ENTITY_HUBSPOT_CAMPAIGN:
        from app.connectors.hubspot import HubSpotAPIError, search_contacts
        from app.connectors.hubspot_oauth import ensure_hubspot_access_token
        from app.connectors.repository import get_connector_by_type

        conn = get_connector_by_type(client, org_id, "hubspot", environment_name="default")
        if not conn:
            return None
        token, err = ensure_hubspot_access_token(
            client,
            org_id,
            str(conn["id"]),
            active_settings,
            environment_name=str(conn.get("environment") or "default"),
        )
        if err or not token:
            return None
        try:
            result = search_contacts(
                token,
                filter_groups=[
                    {
                        "filters": [
                            {
                                "propertyName": "hs_analytics_source_data_1",
                                "operator": "CONTAINS_TOKEN",
                                "value": target_entity_id,
                            }
                        ]
                    }
                ],
                properties=["email"],
                limit=100,
            )
        except HubSpotAPIError as exc:
            logger.warning(
                "marketing_metric_fetch_failed org=%s campaign=%s error=%s",
                org_id,
                target_entity_id,
                exc,
            )
            return None
        total = result.get("total") if isinstance(result.get("total"), int) else len(result.get("results") or [])
        return float(total)

    return None
