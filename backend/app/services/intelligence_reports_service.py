"""Intelligence › Reports: saved views the whole team sees, and scheduled report email.

Both live on ``organizations.settings["intelligenceReports"]`` so no new table
is needed:

- ``views``: up to 50 saved views (template + period), shared with every
  member of the organization. Anyone can save one; the person who saved it or
  an admin can remove it.
- ``schedules``: one schedule per person, keyed by user id. The person picks
  the template, the cadence (Monday, Friday or the first of the month) and the
  local time; the ops notifications tick emails the report when it is due, at
  most once per scheduled slot.

The emailed report is built from the same sources the Reports page reads
(the agent ROI report and the intelligence snapshot). A number with no
evidence is written as "no evidence yet", never as zero.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

from app.core.logging import get_logger

logger = get_logger(__name__)

REPORTS_KEY = "intelligenceReports"
MAX_VIEWS = 50

TEMPLATES: dict[str, str] = {
    "business": "Business",
    "agent": "Agent",
    "prediction": "Prediction",
    "governance": "Governance",
}
PERIODS = (7, 30, 90)
CADENCES: dict[str, str] = {
    "monday": "Monday",
    "friday": "Friday",
    "month_start": "First of the month",
}
TIMES: dict[str, int] = {"08:00": 8, "12:00": 12, "17:00": 17}


class ReportsInputError(ValueError):
    """Raised for a template, period, cadence or time the page does not offer."""


# ---------------------------------------------------------------- storage


def _read_settings(client: Any, org_id: str) -> dict[str, Any] | None:
    try:
        rows = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("intelligence_reports_settings_read_failed org=%s error=%s", org_id, exc)
        return None
    if not rows:
        return None
    raw = rows[0].get("settings")
    return dict(raw) if isinstance(raw, dict) else {}


def _reports_state(settings: dict[str, Any] | None) -> dict[str, Any]:
    raw = (settings or {}).get(REPORTS_KEY)
    state = dict(raw) if isinstance(raw, dict) else {}
    views = state.get("views")
    schedules = state.get("schedules")
    state["views"] = [v for v in views if isinstance(v, dict)] if isinstance(views, list) else []
    state["schedules"] = dict(schedules) if isinstance(schedules, dict) else {}
    return state


def load_reports_state(client: Any, org_id: str) -> dict[str, Any]:
    return _reports_state(_read_settings(client, org_id))


def _save_reports_state(
    client: Any,
    org_id: str,
    update: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    """Write only the intelligenceReports key onto a fresh read of the org settings.

    Re-reading just before the write keeps everything else an admin saved in
    the meantime (approval rules, branding, ops notification state).
    """
    current = _read_settings(client, org_id)
    if current is None:
        return None
    next_state = update(_reports_state(current))
    if next_state is None:
        return None
    current[REPORTS_KEY] = next_state
    client.table("organizations").update({"settings": current}).eq("id", org_id).execute()
    return next_state


# ---------------------------------------------------------------- saved views


def _check_template(template_id: str) -> str:
    value = str(template_id or "").strip().lower()
    if value not in TEMPLATES:
        raise ReportsInputError("Pick one of the report templates: Business, Agent, Prediction or Governance.")
    return value


def _check_period(period_days: int) -> int:
    try:
        value = int(period_days)
    except (TypeError, ValueError) as exc:
        raise ReportsInputError("The period must be 7, 30 or 90 days.") from exc
    if value not in PERIODS:
        raise ReportsInputError("The period must be 7, 30 or 90 days.")
    return value


def public_view(view: dict[str, Any], *, user_id: str, is_admin: bool) -> dict[str, Any]:
    saved_by = str(view.get("savedBy") or "")
    return {
        "id": str(view.get("id") or ""),
        "label": str(view.get("label") or TEMPLATES.get(str(view.get("templateId")), "Saved view")),
        "templateId": str(view.get("templateId") or "business"),
        "periodDays": int(view.get("periodDays") or 30),
        "savedAt": str(view.get("savedAt") or ""),
        "savedByName": str(view.get("savedByName") or "") or None,
        "mine": saved_by == user_id,
        "canRemove": saved_by == user_id or is_admin,
    }


def list_views(client: Any, org_id: str, *, user_id: str, is_admin: bool) -> list[dict[str, Any]]:
    state = load_reports_state(client, org_id)
    return [public_view(v, user_id=user_id, is_admin=is_admin) for v in state["views"] if v.get("id")]


def save_view(
    client: Any,
    org_id: str,
    *,
    user_id: str,
    user_name: str | None,
    template_id: str,
    period_days: int,
    label: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    template = _check_template(template_id)
    period = _check_period(period_days)
    now = now or datetime.now(timezone.utc)
    title = (label or "").strip()[:80] or f"{TEMPLATES[template]} · {period} days"
    view = {
        "id": f"view_{uuid.uuid4().hex[:12]}",
        "label": title,
        "templateId": template,
        "periodDays": period,
        "savedAt": now.isoformat(),
        "savedBy": user_id,
        "savedByName": (user_name or "").strip()[:80] or None,
    }

    def update(state: dict[str, Any]) -> dict[str, Any]:
        # The same template and period saved again replaces the older copy.
        kept = [
            v
            for v in state["views"]
            if not (v.get("templateId") == template and int(v.get("periodDays") or 0) == period)
        ]
        state["views"] = [view, *kept][:MAX_VIEWS]
        return state

    if _save_reports_state(client, org_id, update) is None:
        raise RuntimeError("The view could not be saved. Try again.")
    return view


def delete_view(client: Any, org_id: str, *, view_id: str, user_id: str, is_admin: bool) -> bool:
    """Remove a saved view. Only the person who saved it, or an admin, can."""
    outcome = {"found": False, "allowed": False}

    def update(state: dict[str, Any]) -> dict[str, Any] | None:
        match = next((v for v in state["views"] if str(v.get("id")) == view_id), None)
        if match is None:
            return None
        outcome["found"] = True
        if str(match.get("savedBy") or "") != user_id and not is_admin:
            return None
        outcome["allowed"] = True
        state["views"] = [v for v in state["views"] if str(v.get("id")) != view_id]
        return state

    _save_reports_state(client, org_id, update)
    if outcome["found"] and not outcome["allowed"]:
        raise PermissionError("Only the person who saved this view, or an admin, can remove it.")
    return outcome["allowed"]


# ---------------------------------------------------------------- schedules


def public_schedule(schedule: dict[str, Any] | None) -> dict[str, Any] | None:
    if not schedule:
        return None
    return {
        "templateId": str(schedule.get("templateId") or "business"),
        "periodDays": int(schedule.get("periodDays") or 7),
        "cadence": str(schedule.get("cadence") or "monday"),
        "time": str(schedule.get("time") or "08:00"),
        "enabled": bool(schedule.get("enabled")),
        "timezone": str(schedule.get("timezone") or "UTC"),
        "lastSentAt": schedule.get("lastSentAt"),
        "lastError": schedule.get("lastError"),
    }


def get_schedule(client: Any, org_id: str, *, user_id: str) -> dict[str, Any] | None:
    state = load_reports_state(client, org_id)
    return public_schedule(state["schedules"].get(user_id))


def org_timezone(settings: dict[str, Any] | None) -> str:
    name = str((settings or {}).get("timezone") or "UTC")
    try:
        ZoneInfo(name)
    except Exception:  # noqa: BLE001
        return "UTC"
    return name


def set_schedule(
    client: Any,
    org_id: str,
    *,
    user_id: str,
    template_id: str,
    period_days: int,
    cadence: str,
    time: str,
    enabled: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    template = _check_template(template_id)
    period = _check_period(period_days)
    cadence_key = str(cadence or "").strip().lower()
    if cadence_key not in CADENCES:
        raise ReportsInputError("Pick Monday, Friday or the first of the month.")
    time_key = str(time or "").strip()
    if time_key not in TIMES:
        raise ReportsInputError("Pick 8:00 AM, 12:00 PM or 5:00 PM.")
    now = now or datetime.now(timezone.utc)
    tz_name = org_timezone(_read_settings(client, org_id))
    saved: dict[str, Any] = {}

    def update(state: dict[str, Any]) -> dict[str, Any]:
        previous = state["schedules"].get(user_id) if isinstance(state["schedules"].get(user_id), dict) else {}
        schedule = {
            "templateId": template,
            "periodDays": period,
            "cadence": cadence_key,
            "time": time_key,
            "enabled": bool(enabled),
            "timezone": tz_name,
            "updatedAt": now.isoformat(),
            "lastSentAt": previous.get("lastSentAt"),
            "lastSlot": previous.get("lastSlot"),
            "lastError": None,
        }
        # Turning a schedule on later in a day that is already past its time
        # must not send straight away: mark the current slot as handled.
        local = now.astimezone(ZoneInfo(tz_name))
        slot = due_slot(schedule, local)
        if enabled and slot and previous.get("lastSlot") != slot and not previous.get("enabled"):
            schedule["lastSlot"] = slot
        state["schedules"][user_id] = schedule
        saved.update(schedule)
        return state

    if _save_reports_state(client, org_id, update) is None:
        raise RuntimeError("The schedule could not be saved. Try again.")
    return public_schedule(saved) or {}


def due_slot(schedule: dict[str, Any], local: datetime) -> str | None:
    """The slot key ("2026-10-26") when this schedule is due at ``local``, else None."""
    cadence = str(schedule.get("cadence") or "")
    hour = TIMES.get(str(schedule.get("time") or ""))
    if hour is None or local.hour < hour:
        return None
    if cadence == "monday" and local.weekday() != 0:
        return None
    if cadence == "friday" and local.weekday() != 4:
        return None
    if cadence == "month_start" and local.day != 1:
        return None
    if cadence not in CADENCES:
        return None
    return local.date().isoformat()


# ---------------------------------------------------------------- report body


def _metric_value(totals: dict[str, Any], key: str) -> float | None:
    metric = totals.get(key) if isinstance(totals, dict) else None
    if not isinstance(metric, dict):
        return None
    if str(metric.get("provenance") or "") in {"not_configured", "insufficient_data"}:
        return None
    value = metric.get("value")
    return float(value) if isinstance(value, (int, float)) else None


def _usd(value: float | None) -> str:
    if value is None:
        return "no evidence yet"
    if value >= 1000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def _count(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def build_report_summary(
    template_id: str,
    period_days: int,
    *,
    roi: dict[str, Any] | None,
    metrics: dict[str, Any] | None,
    predictions: list[dict[str, Any]] | None = None,
    decided_approvals: int | None = None,
) -> tuple[str, str]:
    """(headline, summary) for the emailed report. Pure, so it is easy to test."""
    template = template_id if template_id in TEMPLATES else "business"
    totals = (roi or {}).get("orgTotals") or {}
    execution = (metrics or {}).get("execution") or {}
    outcomes = (metrics or {}).get("outcomes") or {}
    forecast = (metrics or {}).get("predictions") or {}
    period = f"the last {period_days} days"
    headline = f"Your {TEMPLATES[template]} report"

    if template == "agent":
        tasks = _count(_metric_value(totals, "tasksCompleted"))
        hours = _metric_value(totals, "estimatedHoursSaved")
        cost = _metric_value(totals, "agentCostUsd")
        parts = [
            f"Agents finished {_plural(tasks, 'task')}" if tasks is not None else "No finished tasks recorded",
            f"saved about {hours:.1f} hours (estimated from task type)" if hours else "time saved: no evidence yet",
            f"and model calls cost {_usd(cost)}",
        ]
        return headline, f"In {period}: " + ", ".join(parts) + "."

    if template == "prediction":
        active = _count(forecast.get("activePredictions"))
        urgent = _count(forecast.get("highPriorityPredictions"))
        titles = [
            text
            for p in (predictions or [])
            if (text := str(p.get("businessStatement") or p.get("title") or "").strip())
        ]
        text = (
            f"Gravitre has {_plural(active, 'active forecast')}"
            + (f", {urgent} of them likely enough to act on" if urgent else "")
            + "."
            if active is not None
            else "No forecasts were available when this report ran."
        )
        if titles:
            text += " Top: " + "; ".join(titles[:3]) + "."
        return headline, text

    if template == "governance":
        waiting = _count(execution.get("awaitingApproval"))
        parts = []
        if decided_approvals is not None:
            parts.append(f"{_plural(decided_approvals, 'request')} decided in {period}")
        parts.append(
            f"{_plural(waiting, 'item')} waiting on a person now" if waiting is not None else "nothing recorded as waiting"
        )
        return headline, "Approvals: " + ", ".join(parts) + ". Nothing runs until someone on your team approves."

    measured = _count(outcomes.get("measuredOutcomes"))
    actions = _count(execution.get("actionsCompleted"))
    revenue = _metric_value(totals, "revenueInfluencedUsd")
    parts = [
        f"{_plural(measured, 'result')} backed by evidence" if measured is not None else "no measured results yet",
        f"{_plural(actions, 'action')} completed" if actions is not None else "no completed actions recorded",
        f"revenue influenced: {_usd(revenue)}",
    ]
    return headline, f"In {period}: " + ", ".join(parts) + "."


def report_path(template_id: str, period_days: int) -> str:
    return f"/intelligence/reports?template={template_id}&period={period_days}"


# ---------------------------------------------------------------- delivery tick


def _decided_approvals(client: Any, org_id: str, since: datetime) -> int | None:
    try:
        result = (
            client.table("approvals")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .in_("status", ["approved", "rejected"])
            .gte("created_at", since.isoformat())
            .limit(1)
            .execute()
        )
        return int(getattr(result, "count", None) or 0)
    except Exception:  # noqa: BLE001
        return None


async def _report_inputs(client: Any, settings: Any, org_id: str, period_days: int) -> dict[str, Any]:
    from app.services.agent_roi_service import fetch_agent_roi
    from app.services.intelligence_projection_service import get_intelligence_projection_service

    inputs: dict[str, Any] = {"roi": None, "metrics": None, "predictions": []}
    try:
        inputs["roi"] = await asyncio.to_thread(fetch_agent_roi, client, org_id, period_days=period_days)
    except Exception as exc:  # noqa: BLE001
        logger.debug("intelligence_report_roi_skipped org=%s error=%s", org_id, exc)
    try:
        snapshot = await get_intelligence_projection_service(settings).build_snapshot(
            org_id, window_hours=min(period_days * 24, 168)
        )
        dumped = snapshot.model_dump() if hasattr(snapshot, "model_dump") else dict(snapshot)
        inputs["metrics"] = dumped.get("metrics")
        inputs["predictions"] = [p for p in dumped.get("predictions") or [] if isinstance(p, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.debug("intelligence_report_snapshot_skipped org=%s error=%s", org_id, exc)
    return inputs


async def run_intelligence_reports_tick(client: Any, settings: Any, *, now: datetime | None = None) -> int:
    """Email every schedule that is due. Each slot is claimed before sending, so a crash cannot double-send.

    Database reads and writes run in a worker thread so the event loop stays free.
    """
    from app.services.notification_email_service import send_notice_email

    now = now or datetime.now(timezone.utc)
    sent = 0
    try:
        orgs = await asyncio.to_thread(
            lambda: client.table("organizations").select("id, settings").limit(1000).execute().data or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("intelligence_reports_org_scan_failed error=%s", exc)
        return 0
    for org in orgs:
        org_id = str(org.get("id") or "")
        state = _reports_state(org.get("settings") if isinstance(org.get("settings"), dict) else {})
        for user_id, schedule in list(state["schedules"].items()):
            if not isinstance(schedule, dict) or not schedule.get("enabled"):
                continue
            try:
                tz = ZoneInfo(str(schedule.get("timezone") or "UTC"))
            except Exception:  # noqa: BLE001
                tz = ZoneInfo("UTC")
            slot = due_slot(schedule, now.astimezone(tz))
            if not slot or schedule.get("lastSlot") == slot:
                continue

            def claim(current: dict[str, Any], uid: str = user_id, key: str = slot) -> dict[str, Any] | None:
                row = current["schedules"].get(uid)
                if not isinstance(row, dict) or not row.get("enabled") or row.get("lastSlot") == key:
                    return None
                current["schedules"][uid] = {**row, "lastSlot": key}
                return current

            if await asyncio.to_thread(_save_reports_state, client, org_id, claim) is None:
                continue
            template = str(schedule.get("templateId") or "business")
            period = int(schedule.get("periodDays") or 7)
            ok = False
            error: str | None = None
            try:
                inputs = await _report_inputs(client, settings, org_id, period)
                decided = (
                    await asyncio.to_thread(_decided_approvals, client, org_id, now - timedelta(days=period))
                    if template == "governance"
                    else None
                )
                headline, summary = build_report_summary(
                    template,
                    period,
                    roi=inputs["roi"],
                    metrics=inputs["metrics"],
                    predictions=inputs["predictions"],
                    decided_approvals=decided,
                )
                ok = await asyncio.to_thread(
                    send_notice_email,
                    client,
                    settings,
                    org_id=org_id,
                    user_id=user_id,
                    headline=headline,
                    summary=summary,
                    view_path=report_path(template, period),
                    cta_label="Open the report",
                )
                if not ok:
                    error = "Email could not be sent. Check that email delivery is set up for your workspace."
            except Exception as exc:  # noqa: BLE001
                logger.warning("intelligence_report_send_failed org=%s user=%s error=%s", org_id, user_id, exc)
                error = "The report could not be built this time."

            def record(current: dict[str, Any], uid: str = user_id) -> dict[str, Any] | None:
                row = current["schedules"].get(uid)
                if not isinstance(row, dict):
                    return None
                patch = {"lastError": error}
                if ok:
                    patch["lastSentAt"] = now.isoformat()
                current["schedules"][uid] = {**row, **patch}
                return current

            await asyncio.to_thread(_save_reports_state, client, org_id, record)
            sent += 1 if ok else 0
    return sent
