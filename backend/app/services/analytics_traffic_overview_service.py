"""Business-intent handler: website traffic overview from connected analytics."""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.clarification_policy import (
    decide_from_resource_resolution,
    format_not_connected_message,
)
from app.services.connector_resource_resolver import ResourceResolution, resolve_resource
from app.services.connector_semantic_registry import (
    connector_display_name,
    mentions_analytics_traffic_language,
    mentions_website_performance_language,
    resolve_all_connectors_from_text,
    resolve_analytics_capabilities_for_message,
    resolve_connector_from_text,
)
from app.services.analytics_followup import (
    GA,
    GSC,
    AnalyticsFollowup,
    analytics_frame,
    analytics_frame_patch,
    resolve_analytics_followup,
)
from app.services.canonical_time_resolver import (
    TimeWindow,
    previous_comparable_window,
    resolve_time_window,
    time_window_from_mapping,
    user_facing_time_label,
)
from app.services.execution_plan_service import (
    execution_plan_patch,
    mark_plan_terminal,
    reconcile_execution_plan,
)
from app.services.reference_resolver import resolve_reference, store_active_analysis
from app.services.sealed_read_execution import (
    ensure_plan_read_step,
    invoke_sealed_f1_read,
    unwrap_report_payload,
)
from app.services.tool_types import ToolContext, ToolValidationError

logger = get_logger(__name__)


def _traffic_date_range(message: str, *, timezone_name: str | None = None) -> tuple[str, str, str]:
    """Compile dates from the canonical time resolver + ActionSpec defaults (not a parallel schema)."""
    window = resolve_time_window(message, timezone_name=timezone_name)
    if window is not None:
        return window.start_iso, window.end_iso, window.interpretation
    from app.connectors.action_catalog.registry import get_action_spec

    spec = get_action_spec("google_analytics.reports.run")
    start, end = "30daysAgo", "today"
    if spec is not None:
        for rule in spec.parameter_source_rules:
            if rule.parameter == "start_date" and rule.default not in (None, ""):
                start = str(rule.default)
            if rule.parameter == "end_date" and rule.default not in (None, ""):
                end = str(rule.default)
    return start, end, "action_spec_default"

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
        from app.services.task_continuity import frame_is_analytics, is_continuity_followup

        if is_continuity_followup(message, task_state) and frame_is_analytics(task_state):
            return AnalyticsTrafficIntent(connector_id="google_analytics", is_followup=True)
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
    # Named website-traffic language with no connected analytics still belongs
    # to this handler so we return connect guidance instead of a web-search detour.
    return AnalyticsTrafficIntent(connector_id="google_analytics")


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


_OVERVIEW_FOLLOW_UP = "Want me to dig into where the visits came from, or which pages did best?"


def _compose_overview_message(
    *,
    property_name: str,
    current: dict[str, Any],
    previous: dict[str, Any],
    timeframe_label: str,
) -> str:
    users = _metric_total(current, "activeUsers")
    prev_users = _metric_total(previous, "activeUsers")
    sessions = _metric_total(current, "sessions")
    prev_sessions = _metric_total(previous, "sessions")
    views = _metric_total(current, "screenPageViews")
    prev_views = _metric_total(previous, "screenPageViews")

    lines = [
        f"Here's how **{property_name}** did over **{timeframe_label}**, "
        "compared with the period before.",
        "",
    ]
    if users is not None:
        change = _pct_change(users, prev_users)
        suffix = f" ({change})" if change else ""
        lines.append(f"- **Visitors:** {int(users):,}{suffix}")
    if sessions is not None:
        change = _pct_change(sessions, prev_sessions)
        suffix = f" ({change})" if change else ""
        lines.append(f"- **Visits:** {int(sessions):,}{suffix}")
    if views is not None:
        change = _pct_change(views, prev_views)
        suffix = f" ({change})" if change else ""
        lines.append(f"- **Page views:** {int(views):,}{suffix}")

    lines.extend(
        [
            "",
            _OVERVIEW_FOLLOW_UP,
        ]
    )
    return "\n".join(lines)


def _ga4_evidence(*, plan_id: str | None, step_id: str | None, report: dict[str, Any]) -> dict[str, Any]:
    """Provider evidence for a GA4 report, so its numbers are not treated as made up."""
    from app.services.provider_result_grounding import evidence_from_observation

    rows = report.get("rows") if isinstance(report, dict) else None
    return evidence_from_observation(
        action_key="google_analytics.reports.run",
        result_count=len(rows) if isinstance(rows, list) else 0,
        observation_id=None,
        plan_id=plan_id,
        step_id=step_id,
        success=True,
        provider_invoked=True,
    )


def _spoken_change(current: float | None, previous: float | None) -> str:
    if current is None or previous is None or previous == 0:
        return ""
    delta = ((current - previous) / abs(previous)) * 100.0
    if abs(delta) < 1:
        return ", about the same as the period before"
    direction = "up" if delta > 0 else "down"
    return f", {direction} {abs(delta):.0f} percent from the period before"


def _spoken_overview(
    *,
    current: dict[str, Any],
    previous: dict[str, Any],
    timeframe_label: str,
    top_source: str | None,
) -> str:
    """The same overview as a person would say it, for voice."""
    users = _metric_total(current, "activeUsers")
    sessions = _metric_total(current, "sessions")
    views = _metric_total(current, "screenPageViews")
    when = timeframe_label.replace("**", "").strip() or "this period"
    if users is None and sessions is None:
        return f"I checked Google Analytics, but there's no traffic recorded for {when}."
    parts: list[str] = []
    if users is not None:
        parts.append(
            f"Over {when}, your site had {int(users):,} visitors"
            f"{_spoken_change(users, _metric_total(previous, 'activeUsers'))}."
        )
    extras = []
    if sessions is not None:
        extras.append(f"{int(sessions):,} visits")
    if views is not None:
        extras.append(f"{int(views):,} page views")
    if extras:
        lead = "That's" if users is not None else f"Over {when}, you had"
        parts.append(f"{lead} {' and '.join(extras)}.")
    if top_source:
        parts.append(f"Most of it came from {top_source}.")
    parts.append("Want me to dig into where it came from, or which pages did best?")
    return " ".join(parts)


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


async def _try_cross_source_website_overview_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None = None,
    window: TimeWindow | None = None,
    sources: tuple[str, ...] | None = None,
) -> dict[str, Any] | None:
    """Phase C — parallel GA4 + GSC reads when both connectors are connected.

    ``window`` and ``sources`` carry a follow-up's edit of the previous answer
    (a corrected period, or one named source); without them the period comes
    from the message and both sources are read.
    """
    from app.services.cognitive_execution_engine import (
        apply_observations_to_plan,
        execute_read_steps_parallel,
    )
    from app.services.cognitive_execution_replanner import build_cross_source_analytics_plan
    from app.services.execution_plan_service import (
        ExecutionObservation,
        ExecutionStep,
        execution_plan_patch,
        observations_patch,
    )
    from app.services.terminal_turn_policy import enforce_terminal_turn_outcome

    plan = build_cross_source_analytics_plan(
        message,
        capability_id="analytics.traffic_overview",
        connected_integrations=connected_integrations,
    )
    if plan is None:
        return None
    if sources:
        plan.steps = [step for step in plan.steps if step.connector_id in sources]
        if not plan.steps:
            return None
    elif len(plan.steps) < 2:
        return None

    async def _handler(step: ExecutionStep, ctx: dict[str, Any]) -> ExecutionObservation:
        if step.connector_id == "google_analytics":
            return await _ga4_read_observation(step, ctx)
        if step.connector_id == "google_search_console":
            return await _gsc_read_observation(step, ctx)
        return ExecutionObservation(
            step_id=step.step_id,
            connector_id=str(step.connector_id or "unknown"),
            success=False,
            summary="Unknown read step",
        )

    ctx = {
        "org_id": org_id,
        "client": client,
        "settings": settings,
        "task_state": {**(task_state or {}), "user_message": message, **execution_plan_patch(plan)},
        "message": message,
        "plan": plan,
        "connected_integrations": list(connected_integrations or []),
        "user_id": user_id,
        "time_window": window,
    }
    observations = await execute_read_steps_parallel(plan, context=ctx, handler=_handler)
    plan = apply_observations_to_plan(plan, observations)
    if not any(o.success for o in observations):
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": enforce_terminal_turn_outcome(
                "I couldn't get your numbers from Google Analytics or Search Console just now. "
                "Want me to try again?",
                task_state=task_state,
                workflow_status="blocked",
            ),
            "task_state": {**(task_state or {}), **execution_plan_patch(plan), **observations_patch(observations)},
            "workflow_status": "blocked",
        }

    message_out = _compose_cross_source_message(observations)
    read_window = window or next(
        (
            time_window_from_mapping((o.structured or {}).get("time_window"))
            for o in observations
            if o.success and isinstance(o.structured, dict) and o.structured.get("time_window")
        ),
        None,
    )
    merged_state = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **observations_patch(observations),
        **analytics_frame_patch(
            message=message,
            window=read_window,
            sources=[o.connector_id for o in observations if o.success],
        ),
    }
    from app.services.structured_assistant_response import blocks_from_execution_observations

    response_blocks = [b.as_dict() for b in blocks_from_execution_observations(
        [o.as_dict() for o in observations]
    )]
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": enforce_terminal_turn_outcome(
            message_out,
            task_state=merged_state,
            workflow_status=str(plan.terminal_status),
        ),
        "task_state": merged_state,
        "workflow_status": plan.terminal_status,
        "business_intent": "analytics.traffic_overview",
        "execution_plan": plan.as_dict(),
        "response_blocks": response_blocks,
        "execution_path": "analytics_traffic_overview",
        "provider_result_evidence": _cross_source_evidence(plan, observations),
        "spoken_message": _spoken_cross_source(observations),
    }


def _cross_source_evidence(plan: Any, observations: list[Any]) -> dict[str, Any] | None:
    from app.services.provider_result_grounding import evidence_from_observation

    ok = next((o for o in observations if getattr(o, "success", False)), None)
    if ok is None:
        return None
    connector = str(getattr(ok, "connector_id", "") or "google_analytics")
    return evidence_from_observation(
        action_key=f"{connector}.reports.run",
        result_count=int(getattr(ok, "result_count", 0) or 0),
        observation_id=getattr(ok, "observation_id", None),
        plan_id=getattr(plan, "plan_id", None),
        step_id=getattr(ok, "step_id", None),
        success=True,
        provider_invoked=True,
    )


async def _ga4_read_observation(step: ExecutionStep, ctx: dict[str, Any]) -> ExecutionObservation:
    from app.services.execution_plan_service import ExecutionObservation, ExecutionPlan

    org_id = str(ctx.get("org_id") or "")
    message = str(ctx.get("message") or "")
    task_state = ctx.get("task_state") if isinstance(ctx.get("task_state"), dict) else {}
    plan = ctx.get("plan")
    if not isinstance(plan, ExecutionPlan):
        plan = ExecutionPlan.from_dict(task_state.get("execution_plan")) or ExecutionPlan(
            plan_id=str(step.step_id),
            summary=message[:240],
            steps=[step],
            source="sealed_read",
            capability_id="analytics.traffic_overview",
        )
    from app.services.sealed_read_execution import attributable_read_actor_id

    actor_id = attributable_read_actor_id(str(ctx.get("user_id") or "") or None) or "analytics-traffic-overview"
    tool_ctx = ToolContext(
        settings=ctx.get("settings"),
        client=ctx.get("client"),
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        capability_id="analytics.traffic_overview",
    )
    _invoked, proof, obs = invoke_sealed_f1_read(
        ctx=tool_ctx,
        action_key="google_analytics.reports.run",
        user_message=message,
        task_state=task_state,
        connected_integrations=list(ctx.get("connected_integrations") or ["google_analytics"]),
        plan=plan,
        step=step,
        proposed_args={"metrics": ["activeUsers", "sessions"]},
        time_window_override=ctx.get("time_window"),
        capability_id="analytics.traffic_overview",
    )
    report = unwrap_report_payload(_invoked.data) if _invoked.success else {}
    users = _metric_total(report, "activeUsers")
    sessions = _metric_total(report, "sessions")
    start_date = str((proof.compiled_parameters or {}).get("start_date") or "")
    end_date = str((proof.compiled_parameters or {}).get("end_date") or "")
    label = user_facing_time_label(proof.time_window, start_date=start_date, end_date=end_date)
    if obs.success:
        obs.summary = f"Analytics: {int(users or 0):,} active users, {int(sessions or 0):,} sessions ({label})"
        obs.structured = {
            **(obs.structured or {}),
            "active_users": users,
            "sessions": sessions,
            "timeframe_label": label,
            "time_window": proof.time_window,
        }
    return obs


async def _gsc_read_observation(step: ExecutionStep, ctx: dict[str, Any]) -> ExecutionObservation:
    from app.services.execution_plan_service import ExecutionPlan

    org_id = str(ctx.get("org_id") or "")
    message = str(ctx.get("message") or "")
    task_state = ctx.get("task_state") if isinstance(ctx.get("task_state"), dict) else {}
    plan = ctx.get("plan")
    if not isinstance(plan, ExecutionPlan):
        plan = ExecutionPlan.from_dict(task_state.get("execution_plan")) or ExecutionPlan(
            plan_id=str(step.step_id),
            summary=message[:240],
            steps=[step],
            source="sealed_read",
            capability_id="analytics.traffic_overview",
        )
    from app.services.sealed_read_execution import attributable_read_actor_id

    actor_id = attributable_read_actor_id(str(ctx.get("user_id") or "") or None) or "analytics-traffic-overview"
    tool_ctx = ToolContext(
        settings=ctx.get("settings"),
        client=ctx.get("client"),
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        step_id=step.step_id,
        capability_id="analytics.traffic_overview",
    )
    _invoked, proof, obs = invoke_sealed_f1_read(
        ctx=tool_ctx,
        action_key="google_search_console.searchAnalytics.query",
        user_message=message,
        task_state=task_state,
        connected_integrations=list(ctx.get("connected_integrations") or ["google_search_console"]),
        plan=plan,
        step=step,
        proposed_args={"dimensions": ["page"], "row_limit": 5},
        time_window_override=ctx.get("time_window"),
        capability_id="analytics.traffic_overview",
    )
    report = unwrap_report_payload(_invoked.data) if _invoked.success else {}
    rows = report.get("rows") or []
    top_page = None
    top_clicks = 0
    for row in rows:
        clicks = int(float((row.get("clicks") or 0)))
        if clicks >= top_clicks:
            top_clicks = clicks
            keys = row.get("keys") or []
            top_page = keys[0] if keys else None
    label = user_facing_time_label(
        proof.time_window,
        start_date=str((proof.compiled_parameters or {}).get("start_date") or ""),
        end_date=str((proof.compiled_parameters or {}).get("end_date") or ""),
    )
    if obs.success:
        obs.summary = (
            f"Search: top page **{top_page}** ({top_clicks:,} clicks, {label})"
            if top_page
            else f"Search: no page clicks in {label}"
        )
        obs.structured = {
            **(obs.structured or {}),
            "top_page": top_page,
            "top_clicks": top_clicks,
            "timeframe_label": label,
            "time_window": proof.time_window,
        }
    return obs


def _compose_cross_source_message(observations: list[Any]) -> str:
    from app.services.execution_plan_service import ExecutionObservation

    ga4 = next(
        (o for o in observations if isinstance(o, ExecutionObservation) and o.connector_id == "google_analytics"),
        None,
    )
    gsc = next(
        (o for o in observations if isinstance(o, ExecutionObservation) and o.connector_id == "google_search_console"),
        None,
    )
    lines = ["Here's how your website's doing:", ""]
    if ga4 and ga4.success:
        summary = ga4.summary.replace("GA4: ", "").replace("Analytics: ", "")
        lines.append(f"- **Analytics:** {summary}")
    elif gsc and gsc.success:
        lines.append(
            "- **Analytics:** Google Analytics isn't connected, so this is search only. "
            "Connect it in Connectors and I can add visits too."
        )
    if gsc and gsc.success:
        summary = gsc.summary.replace("Search Console: ", "").replace("Search: ", "")
        lines.append(f"- **Search:** {summary}")
    elif ga4 and ga4.success:
        lines.append(
            "- **Search:** Search Console isn't connected yet. Connect it in Connectors "
            "and I can add what people searched for."
        )
    lines.append("")
    lines.append("Want me to dig into where the visits came from or which pages did best?")
    return "\n".join(lines)


async def try_analytics_traffic_overview_turn(
    *,
    message: str,
    org_id: str,
    client: Any,
    settings: Settings | None = None,
    connected_integrations: list[str] | None = None,
    task_state: dict[str, Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Execute a READ-only traffic overview or return an honest clarify/connect message."""
    active_settings = settings or get_settings()
    state = task_state if isinstance(task_state, dict) else {}
    pending = state.get("pending_task") if isinstance(state.get("pending_task"), dict) else {}
    if str(pending.get("status") or "").startswith("awaiting") and not is_analytics_traffic_overview_intent(
        message, task_state=task_state
    ):
        # An open approval or question owns this reply ("yes", "the 16th").
        return None
    needs = state.get("cognitive_resolution_needs")
    resolved_message = str(state.get("cognitive_resolution_message") or "").strip()
    # Ingress routing applies to the message it was computed for, not to a
    # later turn that inherited the stored needs.
    e1_routed = (
        isinstance(needs, dict)
        and bool(needs.get("analytics_short_circuit"))
        and (not resolved_message or resolved_message == (message or "").strip())
    )
    followup = resolve_analytics_followup(
        message,
        task_state,
        connected_integrations=connected_integrations,
    )
    if followup is not None and followup.kind == "decline_offer":
        return _declined_offer_turn(message=message, task_state=task_state)
    if followup is not None and followup.breakdowns:
        breakdown = await _try_breakdown_turn(
            message=message,
            followup=followup,
            org_id=org_id,
            client=client,
            settings=active_settings,
            connected_integrations=connected_integrations,
            task_state=task_state,
            user_id=user_id,
        )
        if breakdown is not None:
            return breakdown
    followup_window = followup.window if followup is not None else None
    followup_sources = followup.sources if followup is not None else None
    if e1_routed or followup is not None:
        intent: AnalyticsTrafficIntent | None = AnalyticsTrafficIntent(connector_id="google_analytics")
    else:
        intent = detect_analytics_traffic_intent(
            message,
            task_state=task_state,
            connected_integrations=connected_integrations,
        )
    if intent is None:
        return None
    if followup_sources != (GA,):
        cross = await _try_cross_source_website_overview_turn(
            message=message,
            org_id=org_id,
            client=client,
            settings=active_settings,
            connected_integrations=connected_integrations,
            task_state=task_state,
            user_id=user_id,
            window=followup_window,
            sources=followup_sources,
        )
        if cross is not None:
            return cross

    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    if intent.connector_id not in connected:
        from app.services.website_source_status import (
            any_website_source_executable,
            website_frame_patch,
            website_limitation_message,
            website_source_readiness,
        )

        readiness = website_source_readiness(client, org_id, active_settings)
        if not any_website_source_executable(readiness):
            merged = {**(task_state or {}), **website_frame_patch(objective=message, readiness=readiness)}
            ga_present = bool((readiness.get("google_analytics") or {}).get("present"))
            gsc_present = bool((readiness.get("google_search_console") or {}).get("present"))
            status = "blocked" if (ga_present or gsc_present) else "connector_not_connected"
            from app.services.proactive_business_operator import (
                patch_task_state_with_recommendations,
                rank_safe_read_notices,
                signals_from_website_readiness,
            )

            recs = rank_safe_read_notices(signals_from_website_readiness(readiness))
            return {
                "stop_pipeline": True,
                "dialogue_mode": "answer",
                "message": website_limitation_message(readiness),
                "task_state": patch_task_state_with_recommendations(merged, recs),
                "workflow_status": status,
                "execution_path": "analytics_traffic_overview",
            }
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": format_not_connected_message(
                intent.connector_id,
                display_name=connector_display_name(intent.connector_id),
            ),
            "task_state": {
                **(task_state or {}),
                **website_frame_patch(objective=message, readiness=readiness),
            },
            "workflow_status": "connector_not_connected",
        }

    reference = resolve_reference(message, task_state)
    time_refine = bool(
        re.search(
            r"(?is)\b(last\s+(?:week|month)|this\s+week|yesterday|instead|"
            r"what about last)\b",
            message or "",
        )
    )
    if (
        followup is None
        and reference.matched
        and reference.kind == "referent"
        and reference.referent
        and not time_refine
    ):
        merged = store_active_analysis(task_state or {}, reference.referent)
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "Sure, same site. Which time period, last week or last month?"
            ),
            "task_state": merged,
            "workflow_status": "partial",
            "reference_resolution": reference.reason,
        }
    if reference.matched and reference.kind == "referent" and reference.referent:
        task_state = store_active_analysis(task_state or {}, reference.referent)

    e1_resource = ResourceResolution.from_mapping(
        (task_state or {}).get("e1_resource") if isinstance(task_state, dict) else None
    )
    if e1_resource is not None and e1_resource.connector_id in {
        "",
        intent.connector_id,
        "google_analytics",
    }:
        resolution = e1_resource
    else:
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
                    "Your Google Analytics sign-in has expired, so I can't see your traffic "
                    "right now. Reconnect it in **Connectors** and I'll take another look."
                ),
                "task_state": task_state or {},
                "workflow_status": "blocked",
            }
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "Google Analytics is connected, but I don't know which website to look at yet. "
                "Pick your site under **Connectors → Google Analytics** and I'll take it from there."
            ),
            "task_state": task_state or {},
            "workflow_status": "blocked",
        }

    plan = reconcile_execution_plan(
        message=message,
        task_state=task_state,
        capability_id="analytics.traffic_overview",
        connected_integrations=list(connected),
    )
    plan.execution_strategy = "FAST_PATH"
    plan.capability_id = plan.capability_id or "analytics.traffic_overview"
    primary_step = ensure_plan_read_step(
        plan,
        step_id="read_ga4_primary",
        action_key="google_analytics.reports.run",
        connector_id="google_analytics",
        title="Website traffic",
    )
    previous_step = ensure_plan_read_step(
        plan,
        step_id="read_ga4_previous",
        action_key="google_analytics.reports.run",
        connector_id="google_analytics",
        title="Prior-period traffic",
    )
    source_step = ensure_plan_read_step(
        plan,
        step_id="read_ga4_source",
        action_key="google_analytics.reports.run",
        connector_id="google_analytics",
        title="Traffic sources",
    )

    from app.services.sealed_read_execution import attributable_read_actor_id

    actor_id = attributable_read_actor_id(user_id) or "analytics-traffic-overview"
    tool_ctx = ToolContext(
        settings=active_settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id="analytics.traffic_overview",
        conversation_id=plan.conversation_id,
    )
    try:
        invoked, proof, _obs_primary = invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key="google_analytics.reports.run",
            user_message=message,
            task_state=task_state or {},
            connected_integrations=list(connected),
            plan=plan,
            step=primary_step,
            proposed_args={"metrics": ["activeUsers", "sessions", "screenPageViews"]},
            time_window_override=followup_window,
            capability_id="analytics.traffic_overview",
        )
    except ToolValidationError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": str(exc),
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": "blocked",
            "error_class": getattr(exc, "code", None),
        }
    if not proof.ok:
        from app.services.compiled_task_service import attach_compiled_task

        status = "needs clarification" if proof.error_class == "GENUINE_USER_CLARIFICATION_REQUIRED" else "blocked"
        return {
            "stop_pipeline": True,
            "dialogue_mode": "clarifying" if status == "needs clarification" else "answer",
            "message": proof.user_message(),
            "task_state": attach_compiled_task(
                {**(task_state or {}), **execution_plan_patch(plan)},
                objective_text=message,
                capability_id="analytics.traffic_overview",
                preflight=proof,
                org_id=org_id,
            ),
            "workflow_status": status,
            "preflight_status": proof.status,
            "error_class": proof.error_class,
        }
    if not invoked.success:
        plan = mark_plan_terminal(plan, "failed")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": (
                "Google Analytics didn't give me your numbers just now. Want me to try again?"
            ),
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": "blocked",
        }

    current = unwrap_report_payload(invoked.data)
    property_id = str(proof.compiled_parameters.get("property_id") or "")
    property_name = (proof.resource or {}).get("name") or f"your website"
    start_date = str(proof.compiled_parameters.get("start_date") or "")
    end_date = str(proof.compiled_parameters.get("end_date") or "")
    compiled_window = time_window_from_mapping(proof.time_window)
    if compiled_window is None:
        compiled_window = resolve_time_window(message)
    timeframe_label = user_facing_time_label(
        compiled_window or proof.time_window,
        start_date=start_date,
        end_date=end_date,
    )
    previous_report: dict[str, Any] = {}
    source_report: dict[str, Any] = {}
    if compiled_window is not None:
        prior = previous_comparable_window(compiled_window)

        def _previous_read():
            return invoke_sealed_f1_read(
                ctx=tool_ctx,
                action_key="google_analytics.reports.run",
                user_message=message,
                task_state=task_state or {},
                connected_integrations=list(connected),
                plan=plan,
                step=previous_step,
                proposed_args={"metrics": ["activeUsers", "sessions", "screenPageViews"]},
                time_window_override=prior,
                capability_id="analytics.traffic_overview",
            )

        def _source_read():
            return invoke_sealed_f1_read(
                ctx=tool_ctx,
                action_key="google_analytics.reports.run",
                user_message=message,
                task_state=task_state or {},
                connected_integrations=list(connected),
                plan=plan,
                step=source_step,
                proposed_args={
                    "metrics": ["sessions"],
                    "dimensions": ["sessionDefaultChannelGroup"],
                },
                time_window_override=compiled_window,
                capability_id="analytics.traffic_overview",
            )

        _prev_pack, _src_pack = await asyncio.gather(
            asyncio.to_thread(_previous_read),
            asyncio.to_thread(_source_read),
        )
        _prev_inv, _prev_proof, _ = _prev_pack
        _src_inv, _src_proof, _ = _src_pack
        if _prev_inv.success:
            previous_report = unwrap_report_payload(_prev_inv.data)
        if _src_inv.success:
            source_report = unwrap_report_payload(_src_inv.data)

    message_out = _compose_overview_message(
        property_name=property_name,
        current=current,
        previous=previous_report,
        timeframe_label=timeframe_label,
    )
    source_rows = source_report.get("rows") or []
    top_source: str | None = None
    if source_rows:
        dims = source_rows[0].get("dimensionValues") or []
        source_label = dims[0].get("value") if dims else None
        if source_label and source_label != "(not set)":
            top_source = str(source_label)
            message_out = message_out.replace(
                _OVERVIEW_FOLLOW_UP,
                f"Most visits came from **{source_label}**.\n\n{_OVERVIEW_FOLLOW_UP}",
            )

    analytics_result = {
        "timeframe": timeframe_label,
        "time_window": (compiled_window.as_dict() if compiled_window else proof.time_window),
        "metrics": {
            "active_users": _metric_total(current, "activeUsers"),
            "sessions": _metric_total(current, "sessions"),
            "views": _metric_total(current, "screenPageViews"),
        },
        "sources": source_report,
        "limitations": [],
    }

    state_patch = _session_state_patch(
        property_id=property_id,
        property_name=property_name,
        connector_id=intent.connector_id,
    )
    plan = mark_plan_terminal(plan, "completed")
    merged_state = store_active_analysis(
        {**(task_state or {}), **state_patch, **execution_plan_patch(plan)},
        {
            "kind": "analytics.traffic_overview",
            "connector_id": intent.connector_id,
            "property_id": property_id,
            "property_name": property_name,
        },
    )
    from app.services.compiled_task_service import attach_compiled_task

    merged_state = attach_compiled_task(
        merged_state,
        objective_text=message,
        capability_id="analytics.traffic_overview",
        preflight=proof,
        org_id=org_id,
    )

    from app.services.terminal_turn_policy import enforce_terminal_turn_outcome

    message_out = enforce_terminal_turn_outcome(
        message_out,
        task_state=merged_state,
        workflow_status=str(plan.terminal_status or "completed"),
    )
    from app.services.structured_assistant_response import blocks_from_ga4_reports

    response_blocks = [
        b.as_dict()
        for b in blocks_from_ga4_reports(
            property_name=property_name,
            current=current,
            previous=previous_report,
            timeframe_label=timeframe_label,
        )
    ]
    evidence = _ga4_evidence(
        plan_id=plan.plan_id,
        step_id=primary_step.step_id,
        report=current,
    )
    merged_state = {
        **merged_state,
        "provider_result_evidence": evidence,
        **analytics_frame_patch(
            message=message,
            window=compiled_window or proof.time_window,
            sources=[GA],
        ),
    }
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": message_out,
        "spoken_message": _spoken_overview(
            current=current,
            previous=previous_report,
            timeframe_label=timeframe_label,
            top_source=top_source,
        ),
        "provider_result_evidence": evidence,
        "execution_path": "analytics_traffic_overview",
        "task_state": merged_state,
        "workflow_status": plan.terminal_status,
        "plan_terminal_status": plan.terminal_status,
        "execution_strategy": "FAST_PATH",
        "business_intent": "analytics.traffic_overview",
        "response_blocks": response_blocks,
        "analytics_result": analytics_result,
        "execution_plan": plan.as_dict(),
        "resolution": {
            "connector_id": intent.connector_id,
            "property_id": property_id,
            "property_name": property_name,
            "resolution_reason": (proof.resource or {}).get("reason") or resolution.resolution_reason,
        },
    }


def _declined_offer_turn(*, message: str, task_state: dict[str, Any] | None) -> dict[str, Any]:
    """The user turned down the breakdown offer: acknowledge, run nothing."""
    del message
    frame = dict(analytics_frame(task_state) or {})
    frame["offer"] = []
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": "No problem. Let me know if you want to dig into it later.",
        "task_state": {**(task_state or {}), "analytics_frame": frame},
        "workflow_status": "completed",
        "execution_path": "analytics_traffic_overview",
        "business_intent": "analytics.traffic_overview",
    }


def _report_rows(report: dict[str, Any]) -> list[tuple[str, float]]:
    """(label, first metric) rows from a GA4 or Search Console report."""
    out: list[tuple[str, float]] = []
    for row in report.get("rows") or []:
        if not isinstance(row, dict):
            continue
        dims = row.get("dimensionValues")
        if isinstance(dims, list) and dims:
            label = str((dims[0] or {}).get("value") or "")
            values = row.get("metricValues") or []
            try:
                value = float((values[0] or {}).get("value") or 0) if values else 0.0
            except (TypeError, ValueError):
                value = 0.0
        else:
            keys = row.get("keys") or []
            label = str(keys[0]) if keys else ""
            try:
                value = float(row.get("clicks") or 0)
            except (TypeError, ValueError):
                value = 0.0
        if label and label != "(not set)":
            out.append((label, value))
    out.sort(key=lambda item: item[1], reverse=True)
    return out


async def _try_breakdown_turn(
    *,
    message: str,
    followup: AnalyticsFollowup,
    org_id: str,
    client: Any,
    settings: Settings,
    connected_integrations: list[str] | None,
    task_state: dict[str, Any] | None,
    user_id: str | None,
) -> dict[str, Any] | None:
    """Pages / traffic-source breakdown for the period under discussion."""
    from app.services.sealed_read_execution import attributable_read_actor_id

    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    sources = [s for s in (followup.sources or (GA, GSC)) if s in connected]
    if not sources:
        return None
    reads: list[tuple[str, str, str, dict[str, Any], str]] = []
    for breakdown in followup.breakdowns:
        if breakdown == "pages":
            if GA in sources:
                reads.append(
                    (
                        "pages",
                        GA,
                        "google_analytics.reports.run",
                        {"metrics": ["screenPageViews"], "dimensions": ["pagePath"], "limit": 5},
                        "views",
                    )
                )
            elif GSC in sources:
                reads.append(
                    (
                        "pages",
                        GSC,
                        "google_search_console.searchAnalytics.query",
                        {"dimensions": ["page"], "row_limit": 5},
                        "clicks",
                    )
                )
        elif breakdown == "sources" and GA in sources:
            reads.append(
                (
                    "sources",
                    GA,
                    "google_analytics.reports.run",
                    {"metrics": ["sessions"], "dimensions": ["sessionDefaultChannelGroup"], "limit": 5},
                    "visits",
                )
            )
    if not reads:
        return None

    plan = reconcile_execution_plan(
        message=message,
        task_state=task_state,
        capability_id="analytics.traffic_overview",
        connected_integrations=list(connected),
    )
    plan.execution_strategy = "FAST_PATH"
    plan.capability_id = plan.capability_id or "analytics.traffic_overview"
    actor_id = attributable_read_actor_id(user_id) or "analytics-traffic-overview"
    tool_ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name="production",
        cognitive_invoke=True,
        plan_id=plan.plan_id,
        capability_id="analytics.traffic_overview",
        conversation_id=plan.conversation_id,
    )
    steps = {
        kind: ensure_plan_read_step(
            plan,
            step_id=f"read_{connector}_{kind}",
            action_key=action_key,
            connector_id=connector,
            title="Top pages" if kind == "pages" else "Traffic sources",
        )
        for kind, connector, action_key, _args, _unit in reads
    }

    def _read(kind: str, action_key: str, args: dict[str, Any]):
        return invoke_sealed_f1_read(
            ctx=tool_ctx,
            action_key=action_key,
            user_message=message,
            task_state=task_state or {},
            connected_integrations=list(connected),
            plan=plan,
            step=steps[kind],
            proposed_args=args,
            time_window_override=followup.window,
            capability_id="analytics.traffic_overview",
        )

    try:
        packs = await asyncio.gather(
            *(asyncio.to_thread(_read, kind, action_key, args) for kind, _c, action_key, args, _u in reads)
        )
    except ToolValidationError as exc:
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": str(exc),
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": "blocked",
        }

    sections: list[tuple[str, str, list[tuple[str, float]]]] = []
    window_used: dict[str, Any] | None = followup.window.as_dict() if followup.window else None
    blocked_message: str | None = None
    for (kind, _connector, _action, _args, unit), (invoked, proof, _obs) in zip(reads, packs):
        if not proof.ok:
            blocked_message = blocked_message or proof.user_message()
            continue
        if not invoked.success:
            continue
        window_used = window_used or proof.time_window
        sections.append((kind, unit, _report_rows(unwrap_report_payload(invoked.data))[:5]))

    if not sections:
        plan = mark_plan_terminal(plan, "failed")
        return {
            "stop_pipeline": True,
            "dialogue_mode": "answer",
            "message": blocked_message
            or "I couldn't get that breakdown from your analytics just now. Want me to try again?",
            "task_state": {**(task_state or {}), **execution_plan_patch(plan)},
            "workflow_status": "blocked",
            "execution_path": "analytics_traffic_overview",
        }

    label = user_facing_time_label(window_used).replace("**", "")
    text_lines: list[str] = []
    spoken: list[str] = []
    for kind, unit, rows in sections:
        heading = "Top pages" if kind == "pages" else "Where visits came from"
        if not rows:
            text_lines.append(f"**{heading}:** nothing recorded for {label}.")
            spoken.append(f"I didn't find any {'page' if kind == 'pages' else 'source'} data for {label}.")
            continue
        text_lines.append(f"**{heading}** ({label}):")
        for idx, (name, value) in enumerate(rows, start=1):
            text_lines.append(f"{idx}. {name} — {int(value):,} {unit}")
        text_lines.append("")
        lead_name, lead_value = rows[0]
        if kind == "pages":
            sentence = f"For {label}, your top page was {lead_name} with {int(lead_value):,} {unit}"
        else:
            sentence = f"Most visits came from {lead_name}, {int(lead_value):,} of them"
        if len(rows) > 1:
            sentence += f", then {rows[1][0]} with {int(rows[1][1]):,}"
        spoken.append(sentence + ".")
    message_out = "\n".join(text_lines).strip()

    plan = mark_plan_terminal(plan, "completed")
    merged_state = {
        **(task_state or {}),
        **execution_plan_patch(plan),
        **analytics_frame_patch(message=message, window=window_used, sources=sources, offer=[]),
    }
    merged_state = store_active_analysis(
        merged_state,
        {"kind": "analytics.traffic_overview", "connector_id": sources[0]},
    )
    from app.services.provider_result_grounding import evidence_from_observation

    first_connector = reads[0][1]
    evidence = evidence_from_observation(
        action_key=(
            "google_search_console.searchAnalytics.query"
            if first_connector == GSC
            else "google_analytics.reports.run"
        ),
        result_count=len(sections[0][2]),
        observation_id=None,
        plan_id=plan.plan_id,
        step_id=steps[reads[0][0]].step_id,
        success=True,
        provider_invoked=True,
    )
    merged_state["provider_result_evidence"] = evidence
    return {
        "stop_pipeline": True,
        "dialogue_mode": "answer",
        "message": message_out,
        "spoken_message": " ".join(spoken),
        "provider_result_evidence": evidence,
        "execution_path": "analytics_traffic_overview",
        "task_state": merged_state,
        "workflow_status": plan.terminal_status,
        "plan_terminal_status": plan.terminal_status,
        "execution_strategy": "FAST_PATH",
        "business_intent": "analytics.traffic_overview",
        "execution_plan": plan.as_dict(),
    }


def _spoken_cross_source(observations: list[Any]) -> str:
    """The cross-source answer as a person would say it (no markdown)."""
    parts: list[str] = []
    for obs in observations:
        if not getattr(obs, "success", False):
            continue
        data = obs.structured if isinstance(getattr(obs, "structured", None), dict) else {}
        when = str(data.get("timeframe_label") or "this period").replace("**", "")
        if obs.connector_id == GA and data.get("active_users") is not None:
            parts.append(
                f"Over {when}, your site had {int(data.get('active_users') or 0):,} visitors "
                f"across {int(data.get('sessions') or 0):,} visits."
            )
        elif obs.connector_id == GSC:
            if data.get("top_page"):
                parts.append(
                    f"From search, your top page was {data.get('top_page')} "
                    f"with {int(data.get('top_clicks') or 0):,} clicks."
                )
            else:
                parts.append(f"Search didn't record any page clicks for {when}.")
    if not parts:
        return ""
    parts.append("Want me to dig into where the visits came from, or which pages did best?")
    return " ".join(parts)
