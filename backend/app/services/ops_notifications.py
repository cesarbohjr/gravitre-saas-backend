"""Notifications behind Settings > Notifications and Human in the loop.

- ``notify_source_attention``: a source that just started failing tells the
  org's admins and owners ("A source needs attention").
- ``escalate_past_due_approvals``: with the "Escalate past due requests" rule
  on, a request past its decision SLA notifies admins and owners once.
- ``send_weekly_summaries``: Monday morning in the org's time zone, every
  member gets last week's numbers ("Weekly summary"). Who gets it by email,
  Slack or in app follows each person's notification matrix (in app only by
  default, so nobody starts receiving email they did not ask for).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.core.logging import get_logger
from app.services.notification_emitter import emit_notification
from app.services.org_approval_rules import load_rules_and_timezone, sla_deadline

logger = get_logger(__name__)

_ESCALATED_KEEP = 500
WEEKLY_SUMMARY_HOUR = 9
_OPS_KEY = "opsNotifications"


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def org_member_user_ids(client: Any, org_id: str, roles: list[str]) -> list[str]:
    try:
        rows = (
            client.table("organization_members")
            .select("user_id, role")
            .eq("org_id", org_id)
            .in_("role", roles)
            .limit(200)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops_notify_members_failed org=%s error=%s", org_id, exc)
        return []
    out: list[str] = []
    for row in rows:
        uid = str(row.get("user_id") or "").strip()
        if uid and uid not in out:
            out.append(uid)
    return out


def _notify(
    client: Any,
    org_id: str,
    user_ids: list[str],
    *,
    event_type: str,
    title: str,
    body: str,
    url: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    cta_label: str = "Open in Gravitre",
) -> int:
    sent = 0
    for uid in user_ids:
        try:
            if emit_notification(
                client,
                org_id=org_id,
                user_id=uid,
                event_type=event_type,
                title=title,
                body=body,
                entity_ref={"entity_type": entity_type, "entity_id": entity_id, "result_url": url},
                channel_hints={"bell": True, "email": True, "slack": True},
                email_context={"kind": "notice", "cta_label": cta_label},
            ):
                sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("ops_notify_skipped org=%s user=%s error=%s", org_id, uid, exc)
    return sent


def notify_source_attention(
    client: Any,
    *,
    org_id: str,
    source: dict[str, Any],
    previous_status: str | None,
    error: str | None,
) -> int:
    """Tell admins once when a source goes from working to failing."""
    if str(previous_status or "").lower() == "error":
        return 0
    name = str(source.get("name") or "A source").strip() or "A source"
    detail = (error or "The last sync could not finish.").strip()
    return _notify(
        client,
        org_id,
        org_member_user_ids(client, org_id, ["owner", "admin"]),
        event_type="source_attention",
        title=f"{name} needs attention",
        body=f"{detail} Agents cannot read from it until it is reconnected."[:2000],
        url="/sources",
        entity_type="source",
        entity_id=str(source.get("id") or "") or None,
        cta_label="Open Sources",
    )


def _pending_requests(client: Any, org_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        runs = (
            client.table("workflow_runs")
            .select("id, created_at, definition_snapshot")
            .eq("org_id", org_id)
            .eq("approval_status", "pending_approval")
            .limit(100)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        runs = []
    for run in runs:
        snap = run.get("definition_snapshot") if isinstance(run.get("definition_snapshot"), dict) else {}
        out.append(
            {
                "id": str(run.get("id") or ""),
                "started": run.get("created_at"),
                "title": str(snap.get("name") or "A workflow run"),
            }
        )
    try:
        rows = (
            client.table("approvals")
            .select("id, title, requested_at")
            .eq("org_id", org_id)
            .eq("status", "pending")
            .limit(100)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001
        rows = []
    for row in rows:
        out.append(
            {
                "id": str(row.get("id") or ""),
                "started": row.get("requested_at"),
                "title": str(row.get("title") or "An agent request"),
            }
        )
    return [item for item in out if item["id"]]


def escalate_past_due_approvals(
    client: Any,
    org_id: str,
    *,
    now: datetime | None = None,
    org_settings: dict[str, Any] | None = None,
) -> int:
    """Notify admins once per request that is past its decision SLA.

    Escalated ids are remembered on organizations.settings so each request
    escalates once, however often the tick runs.
    """
    rules, tz_name, _custom = load_rules_and_timezone(client, org_id)
    if not rules.escalate_past_due:
        return 0
    now = now or datetime.now(timezone.utc)
    if org_settings is None:
        org_settings = _org_settings(client, org_id)
    ops = org_settings.get(_OPS_KEY) if isinstance(org_settings.get(_OPS_KEY), dict) else {}
    done = [str(x) for x in (ops.get("escalated") or []) if x]
    due = []
    for item in _pending_requests(client, org_id):
        started = _parse_time(item["started"])
        if started is None or item["id"] in done or sla_deadline(started, rules, tz_name) > now:
            continue
        due.append(item)
    if not due:
        return 0
    # Claim first so a crash mid-send cannot repeat the escalation.
    done = (done + [item["id"] for item in due])[-_ESCALATED_KEEP:]
    org_settings[_OPS_KEY] = {**ops, "escalated": done}
    client.table("organizations").update({"settings": org_settings}).eq("id", org_id).execute()
    approvers = org_member_user_ids(client, org_id, ["owner", "admin"])
    for item in due:
        _notify(
            client,
            org_id,
            approvers,
            event_type="approval_needed",
            title=f"Past due: {item['title']}"[:200],
            body="This request is past its decision SLA and is still waiting on a person.",
            url=f"/approvals?id={item['id']}",
            entity_type="workflow_run",
            entity_id=item["id"],
            cta_label="Open the Decision queue",
        )
    return len(due)


def _org_settings(client: Any, org_id: str) -> dict[str, Any]:
    try:
        rows = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data or []
    except Exception:  # noqa: BLE001
        return {}
    raw = rows[0].get("settings") if rows else None
    return dict(raw) if isinstance(raw, dict) else {}


def _count(client: Any, table: str, org_id: str, since: str, **filters: Any) -> int:
    try:
        q = client.table(table).select("id", count="exact").eq("org_id", org_id).gte("created_at", since)
        for key, value in filters.items():
            q = q.in_(key, value) if isinstance(value, list) else q.eq(key, value)
        result = q.limit(1).execute()
        return int(getattr(result, "count", None) or 0)
    except Exception:  # noqa: BLE001
        return 0


def weekly_summary_text(client: Any, org_id: str, *, now: datetime) -> str:
    since = (now - timedelta(days=7)).isoformat()
    completed = _count(client, "workflow_runs", org_id, since, status="completed")
    failed = _count(client, "workflow_runs", org_id, since, status=["failed", "partial_success"])
    decided = _count(client, "approvals", org_id, since, status=["approved", "rejected"])
    try:
        broken = (
            client.table("rag_sources").select("id", count="exact").eq("org_id", org_id).eq("status", "error")
            .limit(1).execute()
        )
        sources_down = int(getattr(broken, "count", None) or 0)
    except Exception:  # noqa: BLE001
        sources_down = 0
    parts = [
        f"{completed} run{'s' if completed != 1 else ''} completed",
        f"{failed} failed",
        f"{decided} request{'s' if decided != 1 else ''} decided",
    ]
    text = "Last 7 days: " + ", ".join(parts) + "."
    if sources_down:
        text += f" {sources_down} source{'s need' if sources_down != 1 else ' needs'} attention."
    return text


def _week_key(local: datetime) -> str:
    year, week, _ = local.isocalendar()
    return f"{year}-W{week:02d}"


def send_weekly_summary_if_due(client: Any, org: dict[str, Any], *, now: datetime | None = None) -> int:
    """Send once per ISO week, on Monday from 9:00 in the org's time zone."""
    org_id = str(org.get("id") or "")
    org_settings = org.get("settings") if isinstance(org.get("settings"), dict) else {}
    tz_name = str(org_settings.get("timezone") or "UTC")
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(tz)
    if local.weekday() != 0 or local.hour < WEEKLY_SUMMARY_HOUR:
        return 0
    ops = org_settings.get(_OPS_KEY) if isinstance(org_settings.get(_OPS_KEY), dict) else {}
    week = _week_key(local)
    if ops.get("weeklySummaryWeek") == week:
        return 0
    # Claim the week before sending so a crash cannot double-send.
    next_settings = {**org_settings, _OPS_KEY: {**ops, "weeklySummaryWeek": week}}
    client.table("organizations").update({"settings": next_settings}).eq("id", org_id).execute()
    return _notify(
        client,
        org_id,
        org_member_user_ids(client, org_id, ["owner", "admin", "member"]),
        event_type="weekly_summary",
        title="Your weekly summary",
        body=weekly_summary_text(client, org_id, now=now),
        url="/activity",
        cta_label="Open Activity",
    )


def run_ops_notifications_tick(client: Any, *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    escalated = 0
    summaries = 0
    try:
        orgs = client.table("organizations").select("id, settings").limit(1000).execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("ops_notifications_org_scan_failed error=%s", exc)
        return {"orgs": 0, "escalated": 0, "summaries": 0}
    for org in orgs:
        org_id = str(org.get("id") or "")
        if not org_id:
            continue
        settings = org.get("settings") if isinstance(org.get("settings"), dict) else {}
        rules = settings.get("approvalRules") if isinstance(settings.get("approvalRules"), dict) else {}
        try:
            if rules.get("escalatePastDue") is True:
                escalated += escalate_past_due_approvals(client, org_id, now=now, org_settings=dict(settings))
                settings = _org_settings(client, org_id) or settings
            summaries += send_weekly_summary_if_due(client, {"id": org_id, "settings": settings}, now=now)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ops_notifications_org_failed org=%s error=%s", org_id, exc)
    return {"orgs": len(orgs), "escalated": escalated, "summaries": summaries}
