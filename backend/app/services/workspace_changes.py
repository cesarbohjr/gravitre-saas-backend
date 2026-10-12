"""What changed in the user's workspace over a period, read before the model answers.

"What changed in my workspace since yesterday?" used to reach the model with no
dated workspace evidence at all, so it answered that it lacked evidence and
offered to check the very sources the user had asked about (2026-10-12
incident). This module recognises that class of question, resolves the period
in the org's time zone, and reads the workspace's own dated records:
connector activity, workflow runs, approvals, goals, connector health and the
audit log. Each source reports what it found, that it found nothing, or that
it could not be read, so the answer can tell those apart.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# One slow source must not hold the answer; it is reported as not read.
SOURCE_TIMEOUT_S = 2.5
MAX_ITEMS_PER_SOURCE = 8

_CHANGE_RE = re.compile(
    r"(?i)\b(?:what(?:'s|\s+has|\s+have)?\s+(?:changed|happened|new|gone\s+on|been\s+going\s+on|moved)|"
    r"anything\s+(?:new|changed?|happen(?:ed)?)|any\s+(?:changes|updates|news)|catch\s+me\s+up|"
    r"what\s+did\s+i\s+miss|while\s+i\s+was\s+(?:away|out|gone)|recap\s+(?:of\s+)?(?:yesterday|today|the\s+(?:day|week))|"
    r"(?:summary|summari[sz]e)\s+(?:of\s+)?(?:yesterday|today|the\s+(?:day|week)|activity)|recent\s+activity)\b"
)


def is_workspace_change_question(message: str | None) -> bool:
    """True for "what changed / what happened / catch me up" about the user's own workspace."""
    from app.services.adaptive_research_cascade import is_tenant_local_question

    text = str(message or "").strip()
    if not text or not _CHANGE_RE.search(text):
        return False
    return is_tenant_local_question(text) or bool(re.search(r"(?i)\b(?:catch\s+me\s+up|what\s+did\s+i\s+miss)\b", text))


@dataclass
class ChangeWindow:
    start: datetime
    end: datetime
    tz_name: str
    label: str


def resolve_change_window(message: str | None, *, tz_name: str = "UTC", now: datetime | None = None) -> ChangeWindow:
    """The period the question asks about, in the org's time zone.

    "since yesterday" starts at local midnight yesterday; "today" at local
    midnight; "this week" on Monday; "last N hours/days" is rolling. With no
    period named, the last 24 hours.
    """
    try:
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:  # noqa: BLE001
        tz, tz_name = ZoneInfo("UTC"), "UTC"
    end = (now or datetime.now(timezone.utc)).astimezone(tz)
    text = str(message or "").lower()
    midnight = end.replace(hour=0, minute=0, second=0, microsecond=0)

    m = re.search(r"\b(?:last|past)\s+(\d+)\s+(hour|day|week)s?\b", text)
    if m:
        n = max(1, min(int(m.group(1)), 90))
        unit = {"hour": timedelta(hours=1), "day": timedelta(days=1), "week": timedelta(weeks=1)}[m.group(2)]
        start, label = end - n * unit, f"the last {n} {m.group(2)}{'s' if n != 1 else ''}"
    elif re.search(r"\b(?:yesterday)\b", text):
        start, label = midnight - timedelta(days=1), "since the start of yesterday"
    elif re.search(r"\b(?:last\s+night|overnight)\b", text):
        start, label = midnight - timedelta(hours=6), "since 6 PM yesterday"
    elif re.search(r"\b(?:today|this\s+morning|this\s+afternoon|tonight)\b", text):
        start, label = midnight, "since midnight today"
    elif re.search(r"\bthis\s+week\b", text):
        start, label = midnight - timedelta(days=end.weekday()), "since Monday"
    elif re.search(r"\b(?:last|past)\s+week\b", text):
        start, label = end - timedelta(days=7), "the last 7 days"
    elif re.search(r"\bthis\s+month\b", text):
        start, label = midnight.replace(day=1), "since the 1st of this month"
    elif re.search(r"\b(?:last|past)\s+month\b", text):
        start, label = end - timedelta(days=30), "the last 30 days"
    else:
        start, label = end - timedelta(hours=24), "the last 24 hours"
    return ChangeWindow(start=start, end=end, tz_name=tz_name, label=label)


@dataclass
class SourceResult:
    name: str
    status: str  # "read" | "failed"
    total: int = 0
    items: list[str] = field(default_factory=list)


@dataclass
class WorkspaceChanges:
    window: ChangeWindow
    sources: list[SourceResult]

    @property
    def read(self) -> list[SourceResult]:
        return [s for s in self.sources if s.status == "read"]

    @property
    def failed(self) -> list[SourceResult]:
        return [s for s in self.sources if s.status != "read"]

    def to_meta(self) -> dict[str, Any]:
        return {
            "window_start": self.window.start.isoformat(),
            "window_end": self.window.end.isoformat(),
            "timezone": self.window.tz_name,
            "sources": {s.name: {"status": s.status, "total": s.total} for s in self.sources},
        }

    def to_prompt_block(self) -> str:
        w = self.window
        lines = [
            "WORKSPACE CHANGES (read from this workspace's own records for this question; authoritative):",
            f"Period: {w.label} — {_fmt(w.start, w.tz_name, date=True)} to {_fmt(w.end, w.tz_name, date=True)} ({w.tz_name}).",
        ]
        for s in self.sources:
            if s.status != "read":
                continue
            if not s.total:
                lines.append(f"- {s.name}: nothing recorded in this period.")
                continue
            more = f" (showing {len(s.items)} of {s.total})" if s.total > len(s.items) else ""
            lines.append(f"- {s.name}: {s.total}{more}")
            lines.extend(f"    • {item}" for item in s.items)
        if self.failed:
            lines.append("Could not be read this time: " + ", ".join(s.name for s in self.failed) + ".")
        lines.append(
            "Answer from this list: lead with the concrete changes (what, when, status), grouped by area, "
            "most important first. Say which areas had nothing recorded and which could not be read. "
            "These sources have already been checked, so do not offer to check them, do not ask whether "
            "to look, and do not say you lack evidence for what is listed. Gravitre only sees what it "
            "records; changes made directly inside connected apps may not appear here, and you may say so once."
        )
        return "\n".join(lines)


def _fmt(value: datetime | str | None, tz_name: str, *, date: bool = False) -> str:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return "unknown time"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(ZoneInfo(tz_name))
    clock = local.strftime("%I:%M %p").lstrip("0")
    return f"{local.strftime('%a %b')} {local.day}, {clock}" if date else f"{local.strftime('%a')} {clock}"


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None) or []
    return [r for r in data if isinstance(r, dict)]


def _since(query: Any, column: str, start: datetime) -> Any:
    return query.gte(column, start.astimezone(timezone.utc).isoformat())


def _read_activity(client: Any, org_id: str, w: ChangeWindow, user_id: str = "") -> tuple[int, list[str]]:
    # Connected-app actions are the user's own (same scope as the activity feed).
    if not user_id:
        raise ValueError("activity is per user and no user is known")
    rows = _rows(
        _since(
            client.table("activity_events")
            .select("title,status,integration,source,created_at")
            .eq("org_id", org_id)
            .eq("user_id", user_id),
            "created_at",
            w.start,
        )
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    items = []
    for r in rows[:MAX_ITEMS_PER_SOURCE]:
        where = f" in {r['integration']}" if r.get("integration") else ""
        items.append(f"{_fmt(r.get('created_at'), w.tz_name)} — {r.get('title') or 'Activity'}{where} ({r.get('status') or 'completed'})")
    return len(rows), items


def _read_workflow_runs(client: Any, org_id: str, w: ChangeWindow) -> tuple[int, list[str]]:
    rows = _rows(
        _since(
            client.table("workflow_runs")
            .select("workflow_id,status,run_type,created_at,completed_at,error_message")
            .eq("org_id", org_id),
            "created_at",
            w.start,
        )
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    names: dict[str, str] = {}
    ids = list({str(r["workflow_id"]) for r in rows if r.get("workflow_id")})
    if ids:
        try:
            names = {
                str(d["id"]): str(d.get("name") or "")
                for d in _rows(client.table("workflow_defs").select("id,name").eq("org_id", org_id).in_("id", ids).execute())
            }
        except Exception:  # noqa: BLE001
            names = {}
    counts: dict[str, int] = {}
    for r in rows:
        counts[str(r.get("status") or "unknown")] = counts.get(str(r.get("status") or "unknown"), 0) + 1
    items = []
    if counts:
        items.append("By status: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))))
    # Failures first: they are what the user most needs to hear about.
    ordered = sorted(rows, key=lambda r: 0 if r.get("status") == "failed" else 1)
    for r in ordered[: MAX_ITEMS_PER_SOURCE - 1]:
        name = names.get(str(r.get("workflow_id") or "")) or "Unnamed workflow"
        err = f" — {str(r['error_message'])[:120]}" if r.get("status") == "failed" and r.get("error_message") else ""
        dry = " (dry run)" if r.get("run_type") == "dry_run" else ""
        items.append(f"{_fmt(r.get('created_at'), w.tz_name)} — {name}{dry}: {r.get('status')}{err}")
    return len(rows), items


def _read_approvals(client: Any, org_id: str, w: ChangeWindow) -> tuple[int, list[str]]:
    rows = _rows(
        _since(
            client.table("approvals").select("title,status,type,requested_at,reviewed_at,updated_at").eq("org_id", org_id),
            "updated_at",
            w.start,
        )
        .order("updated_at", desc=True)
        .limit(50)
        .execute()
    )
    items = [
        f"{_fmt(r.get('reviewed_at') or r.get('updated_at'), w.tz_name)} — {r.get('title') or 'Approval'}: {r.get('status') or 'pending'}"
        for r in rows[:MAX_ITEMS_PER_SOURCE]
    ]
    return len(rows), items


def _read_goals(client: Any, org_id: str, w: ChangeWindow) -> tuple[int, list[str]]:
    rows = _rows(_since(client.table("goals").select("*").eq("org_id", org_id), "updated_at", w.start).order("updated_at", desc=True).limit(30).execute())
    items = [
        f"{_fmt(r.get('updated_at'), w.tz_name)} — {r.get('title') or r.get('name') or 'Goal'}: {r.get('status') or 'updated'}"
        for r in rows[:MAX_ITEMS_PER_SOURCE]
    ]
    return len(rows), items


def _read_connectors(client: Any, org_id: str, w: ChangeWindow) -> tuple[int, list[str]]:
    rows = _rows(_since(client.table("connectors").select("*").eq("org_id", org_id), "updated_at", w.start).order("updated_at", desc=True).limit(30).execute())
    items = []
    for r in rows[:MAX_ITEMS_PER_SOURCE]:
        name = r.get("name") or r.get("vendor") or r.get("type") or "Connector"
        items.append(f"{_fmt(r.get('updated_at'), w.tz_name)} — {name}: {r.get('status') or 'updated'}")
    return len(rows), items


def _read_audit(client: Any, org_id: str, w: ChangeWindow) -> tuple[int, list[str]]:
    rows = _rows(
        _since(client.table("audit_events").select("action,resource_type,created_at").eq("org_id", org_id), "created_at", w.start)
        .order("created_at", desc=True)
        .limit(200)
        .execute()
    )
    counts: dict[str, int] = {}
    for r in rows:
        key = f"{r.get('action') or 'change'} on {r.get('resource_type') or 'item'}"
        counts[key] = counts.get(key, 0) + 1
    items = [f"{key}: {n}" for key, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_ITEMS_PER_SOURCE]]
    return len(rows), items


_SOURCES: tuple[tuple[str, Callable[..., tuple[int, list[str]]]], ...] = (
    ("Your connected-app actions", _read_activity),
    ("Workflow runs", _read_workflow_runs),
    ("Approvals", _read_approvals),
    ("Goals", _read_goals),
    ("Connectors", _read_connectors),
    ("Audit log", _read_audit),
)


async def read_workspace_changes(
    client: Any,
    org_id: str,
    message: str,
    *,
    user_id: str,
    tz_name: str | None = None,
    now: datetime | None = None,
) -> WorkspaceChanges:
    """Read every workspace source for the asked period, concurrently and bounded."""
    if tz_name is None:
        try:
            from app.services.org_approval_rules import load_org_timezone

            tz_name = await asyncio.wait_for(asyncio.to_thread(load_org_timezone, client, org_id), timeout=1.0)
        except Exception:  # noqa: BLE001
            tz_name = "UTC"
    window = resolve_change_window(message, tz_name=tz_name or "UTC", now=now)

    async def _one(name: str, reader: Callable[..., tuple[int, list[str]]]) -> SourceResult:
        try:
            args = (client, org_id, window, user_id) if reader is _read_activity else (client, org_id, window)
            total, items = await asyncio.wait_for(asyncio.to_thread(reader, *args), timeout=SOURCE_TIMEOUT_S)
            return SourceResult(name=name, status="read", total=total, items=items)
        except Exception as exc:  # noqa: BLE001
            logger.warning("workspace_changes_source_failed org_id=%s source=%s error=%s", org_id, name, str(exc)[:200])
            return SourceResult(name=name, status="failed")

    results = await asyncio.gather(*(_one(name, reader) for name, reader in _SOURCES))
    return WorkspaceChanges(window=window, sources=list(results))
