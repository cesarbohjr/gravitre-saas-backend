"""Business-intent handler: website traffic overview from connected analytics."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.clarification_policy import (
    decide_from_resource_resolution,
    format_not_connected_message,
)
from app.services.connector_resource_resolver import resolve_resource
from app.services.connector_semantic_registry import (
    connector_display_name,
    mentions_analytics_traffic_language,
    mentions_website_performance_language,
    resolve_all_connectors_from_text,
    resolve_analytics_capabilities_for_message,
    resolve_connector_from_text,
)
from app.services.reference_resolver import resolve_reference, store_active_analysis

logger = get_logger(__name__)

# Broad business questions about website / analytics performance.
_ANALYTICS_TRAFFIC_OVERVIEW = re.compile(
    r"(?is)"
    r"(?:"
    r"\b(?:tell\s+me\s+about|how\s+is|what(?:'s|\s+is)\s+(?:happening\s+with|going\s+on\s+with))\s+"
    r"(?:my\s+)?(?:ga4|google\s+analytics|analytics|website)\s+(?:traffic|visitors?|performance|stats?|numbers?|doing)\b"
    r"|"
    r"\b(?:ga4|google\s+analytics)\s+(?:website\s+)?(?:traffic|visitors?|stats?)\b"
    r"|"
    r"\b(?:my\s+)?website\s+(?:traffic|visitors?|performance|analytics|stats?)\b"
    r"|"
    r"\bhow\s+is\s+(?:my\s+)?website\s+doing\b"
    r"|"
    r"\b(?:show|give)\s+me\s+(?:my\s+)?(?:ga4|analytics|website)\s+(?:traffic|stats?|numbers?)\b"
    r")",
)

_FOLLOWUP_ALL_REPORTS = re.compile(
    r"(?is)^\s*(?:all\s+3|all\s+three|all\s+of\s+(?:them|those)|everything|yes\s+all)\s*[.!]?$",
)


@dataclass(frozen=True)
class AnalyticsTrafficIntent:
    connector_id: str
    is_followup: bool = False


def is_analytics_traffic_overview_intent(message: str, *, task_state: dict[str, Any] | None = None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _ANALYTICS_TRAFFIC_OVERVIEW.search(text):
        return True
    if _FOLLOWUP_ALL_REPORTS.match(text):
        session = (task_state or {}).get("connector_session") or {}
        active = session.get("activeEntities") if isinstance(session, dict) else {}
        if isinstance(active, dict) and active.get("analytics_traffic_overview"):
            return True
    # GA4/Analytics mention + traffic language without an action verb menu request.
    if resolve_connector_from_text(text) == "google_analytics" and mentions_analytics_traffic_language(text):
        return True
    if "ga4" in text.lower() and mentions_analytics_traffic_language(text):
        return True
    return False


def detect_analytics_traffic_intent(
    message: str,
    *,
    task_state: dict[str, Any] | None = None,
    connected_integrations: list[str] | None = None,
) -> AnalyticsTrafficIntent | None:
    if not is_analytics_traffic_overview_intent(message, task_state=task_state):
        return None
    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    explicit = resolve_all_connectors_from_text(message)
    if explicit:
        for vendor in explicit:
            if vendor == "google_analytics":
                return AnalyticsTrafficIntent(connector_id=vendor, is_followup=_FOLLOWUP_ALL_REPORTS.match(message or "") is not None)
        # User named a different vendor explicitly — not this handler.
        return None
    if "google_analytics" in connected:
        return AnalyticsTrafficIntent(
            connector_id="google_analytics",
            is_followup=_FOLLOWUP_ALL_REPORTS.match(message or "") is not None,
        )
    if resolve_connector_from_text(message) == "google_analytics":
        return AnalyticsTrafficIntent(connector_id="google_analytics")
    if mentions_analytics_traffic_language(message) and "google_analytics" in connected:
        return AnalyticsTrafficIntent(connector_id="google_analytics")
    if mentions_website_performance_language(message) and "google_analytics" in connected:
        return AnalyticsTrafficIntent(connector_id="google_analytics")
    caps = resolve_analytics_capabilities_for_message(message, connected_integrations=list(connected))
    if caps and caps[0] == "google_analytics":
        return AnalyticsTrafficIntent(connector_id="google_analytics")
    return None


def should_suppress_knowledge_base_for_turn(
    message: str,
    *,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None = None,
) -> bool:
    """Prefer live connector reads over KB when a resolvable analytics ask is in flight."""
    intent = detect_analytics_traffic_intent(
        message,
        task_state=task_state,
        connected_integrations=connected_integrations,
    )
    if intent is None:
        return False
    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    return intent.connector_id in connected


def _metric_total(report: dict[str, Any], metric_name: str) -> float | None:
    headers = report.get("metricHeaders") or []
    idx = next(
        (i for i, header in enumerate(headers) if str(header.get("name") or "") == metric_name),
        None,
    )
    if idx is None:
        return None
    totals = report.get("totals") or []
    if totals:
        values = totals[0].get("metricValues") or []
        if idx < len(values):
            try:
                return float(values[idx].get("value"))
            except (TypeError, ValueError):
                return None
    rows = report.get("rows") or []
    if len(rows) == 1:
        values = rows[0].get("metricValues") or []
        if idx < len(values):
            try:
                return float(values[idx].get("value"))
            except (TypeError, ValueError):
                return None
    total = 0.0
    found = False
    for row in rows:
        values = row.get("metricValues") or []
        if idx >= len(values):
            continue
        try:
            total += float(values[idx].get("value") or 0)
            found = True
        except (TypeError, ValueError):
            continue
    return total if found else None


def _pct_change(current: float | None, previous: float | None) -> str | None:
    if current is None or previous is None or previous == 0:
        return None
    delta = ((current - previous) / abs(previous)) * 100.0
    arrow = "↑" if delta >= 0 else "↓"
    return f"{arrow} {abs(delta):.0f}%"


def _compose_overview_message(
    *,
    property_name: str,
    current: dict[str, Any],
    previous: dict[str, Any],
) -> str:
    users = _metric_total(current, "activeUsers")
    prev_users = _metric_total(previous, "activeUsers")
    sessions = _metric_total(current, "sessions")
    prev_sessions = _metric_total(previous, "sessions")
    views = _metric_total(current, "screenPageViews")
    prev_views = _metric_total(previous, "screenPageViews")

    lines = [
        f"Here's how **{property_name}** performed over the **last 30 days** "
        "compared with the previous 30.",
        "",
    ]
    if users is not None:
        change = _pct_change(users, prev_users)
        suffix = f" ({change})" if change else ""
        lines.append(f"- **Active users:** {int(users):,}{suffix}")
    if sessions is not None:
        change = _pct_change(sessions, prev_sessions)
        suffix = f" ({change})" if change else ""
        lines.append(f"- **Sessions:** {int(sessions):,}{suffix}")
    if views is not None:
        change = _pct_change(views, prev_views)
        suffix = f" ({change})" if change else ""
        lines.append(f"- **Views:** {int(views):,}{suffix}")

    lines.extend(
        [
            "",
            "Want me to break this down by source, page, or conversion?",
        ]
    )
    return "\n".join(lines)


def _session_state_patch(
    *,
    property_id: str,
    property_name: str,
    connector_id: str,
) -> dict[str, Any]:
    return {
        "connector_session": {
            "activeEntities": {
                "analytics_traffic_overview": {
                    "connectorId": connector_id,
                    "propertyId": property_id,
                    "propertyName": property_name,
                }
            },
            "resolvedEntities": {
                "property_id": property_id,
                "google_analytics_property": property_name,
            },
        },
        "resolved_entities": {
            "property_id": property_id,
            "google_analytics_property": property_name,
        },
    }


async def try_analytics_traffic_overview_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None = None,
    connected_integrations: list[str] | None = None,
    task_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Execute a READ-only traffic overview or return an honest clarify/connect message."""
    active_settings = settings or get_settings()
    intent = detect_analytics_traffic_intent(
        message,
        task_state=task_state,
        connected_integrations=connected_integrations,
    )
    if intent is None:
        return None

    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    if intent.connector_id not in connected:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_not_connected_message(
                intent.connector_id,
                display_name=connector_display_name(intent.connector_id),
            ),
            "task_state": task_state or {},
            "workflow_status": "connector_not_connected",
        }

    reference = resolve_reference(message, task_state)
    if reference.matched and reference.kind == "referent" and reference.referent:
        # Follow-up like "compare that to last month" — referent resolved; caller may extend.
        merged = store_active_analysis(task_state or {}, reference.referent)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "I'll use your previous analysis as the baseline. "
                "Comparison reporting across periods is rolling out — "
                "ask again for a fresh traffic overview if you need updated numbers."
            ),
            "task_state": merged,
            "workflow_status": "partial",
            "reference_resolution": reference.reason,
        }

    resolution = resolve_resource(
        connector_id=intent.connector_id,
        client=client,
        org_id=org_id,
        settings=active_settings,
        conversation_context=task_state,
    )
    if resolution.status == "ambiguous":
        decision = decide_from_resource_resolution(
            resolution,
            resource_label="Google Analytics property",
        )
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying",
            "message": decision.message or "",
            "task_state": task_state or {},
            "workflow_status": "needs clarification",
        }

    if resolution.status != "resolved" or not resolution.resource_id:
        if resolution.status == "not_authorized":
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": (
                    "Google Analytics is connected but needs re-authorization before I can "
                    "read traffic. Open **Connectors** and refresh the Google Analytics connection."
                ),
                "task_state": task_state or {},
                "workflow_status": "blocked",
            }
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "Google Analytics is connected, but no GA4 property is linked yet. "
                "Open **Connectors → Google Analytics** and link your property — "
                "if you only have one, we'll select it automatically."
            ),
            "task_state": task_state or {},
            "workflow_status": "blocked",
        }

    from app.connectors.google_analytics import GoogleAnalyticsAPIError, run_ga4_report
    from app.connectors.google_analytics_oauth import ensure_google_analytics_session

    token, err = ensure_google_analytics_session(
        client,
        org_id,
        str(resolution.connection_id or ""),
        active_settings,
    )
    if err or not token:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "I couldn't refresh the Google Analytics session to pull live traffic. "
                "Try reconnecting at /connectors."
            ),
            "task_state": task_state or {},
            "workflow_status": "blocked",
        }

    property_id = resolution.resource_id
    property_name = resolution.display_name or f"Property {property_id}"
    metrics = ["activeUsers", "sessions", "screenPageViews"]
    try:
        current = run_ga4_report(
            token,
            property_id,
            start_date="30daysAgo",
            end_date="today",
            metrics=metrics,
        )
        previous = run_ga4_report(
            token,
            property_id,
            start_date="60daysAgo",
            end_date="31daysAgo",
            metrics=metrics,
        )
        source_report = run_ga4_report(
            token,
            property_id,
            start_date="30daysAgo",
            end_date="today",
            dimensions=["sessionDefaultChannelGroup"],
            metrics=["sessions"],
        )
    except GoogleAnalyticsAPIError as exc:
        logger.warning("ga4_traffic_overview_failed org=%s property=%s err=%s", org_id, property_id, exc)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "Google Analytics is connected, but the traffic report request failed. "
                f"Provider returned: {str(exc)[:200]}"
            ),
            "task_state": task_state or {},
            "workflow_status": "blocked",
        }

    message_out = _compose_overview_message(
        property_name=property_name,
        current=current,
        previous=previous,
    )
    source_rows = source_report.get("rows") or []
    if source_rows:
        dims = source_rows[0].get("dimensionValues") or []
        source_label = dims[0].get("value") if dims else None
        if source_label and source_label != "(not set)":
            message_out = message_out.replace(
                "Want me to break this down by source, page, or conversion?",
                f"Top traffic source in the last 30 days: **{source_label}**.\n\n"
                "Want me to break this down by source, page, or conversion?",
            )

    state_patch = _session_state_patch(
        property_id=property_id,
        property_name=property_name,
        connector_id=intent.connector_id,
    )
    merged_state = store_active_analysis(
        {**(task_state or {}), **state_patch},
        {
            "kind": "analytics.traffic_overview",
            "connector_id": intent.connector_id,
            "property_id": property_id,
            "property_name": property_name,
        },
    )

    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": message_out,
        "task_state": merged_state,
        "workflow_status": "completed",
        "business_intent": "analytics.traffic_overview",
        "resolution": {
            "connector_id": intent.connector_id,
            "property_id": property_id,
            "property_name": property_name,
            "resolution_reason": resolution.resolution_reason,
        },
    }
