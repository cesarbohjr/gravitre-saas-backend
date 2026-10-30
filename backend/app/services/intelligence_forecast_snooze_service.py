"""Intelligence › Forecasts: snoozing a forecast for the whole team.

A snooze hides one forecast from Forecasts until a date, then it comes back on
its own if it is still open. Snoozes live on
``organizations.settings["intelligenceForecastSnoozes"]`` keyed by the
forecast key the page shows, so no table is needed. Expired snoozes are
dropped whenever the list is written.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

SNOOZE_KEY = "intelligenceForecastSnoozes"
SNOOZE_DAYS = (1, 7, 30)
MAX_SNOOZES = 200
AUDIT_ACTION = "intelligence.forecast_snoozed"


class SnoozeInputError(ValueError):
    """Raised for a forecast key or length the page does not offer."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read_settings(client: Any, org_id: str) -> dict[str, Any] | None:
    try:
        rows = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("forecast_snooze_settings_read_failed org=%s error=%s", org_id, exc)
        return None
    if not rows:
        return None
    raw = rows[0].get("settings")
    return dict(raw) if isinstance(raw, dict) else {}


def _parse(value: Any) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo else at.replace(tzinfo=timezone.utc)


def active_snoozes(settings: dict[str, Any] | None, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    """Snoozes that have not run out yet, keyed by forecast key."""
    now = now or _now()
    raw = (settings or {}).get(SNOOZE_KEY)
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(raw, dict):
        return out
    for key, row in raw.items():
        if not isinstance(row, dict):
            continue
        until = _parse(row.get("until"))
        if until and until > now:
            out[str(key)] = row
    return out


def list_snoozes(client: Any, org_id: str, now: datetime | None = None) -> list[dict[str, Any]]:
    rows = active_snoozes(_read_settings(client, org_id), now)
    return [
        {"key": key, "until": row.get("until"), "title": row.get("title") or "", "by": row.get("byName") or ""}
        for key, row in sorted(rows.items(), key=lambda kv: str(kv[1].get("until")))
    ]


def _clean_key(key: str) -> str:
    key = str(key or "").strip()
    if not key or len(key) > 200:
        raise SnoozeInputError("Pick a forecast to snooze.")
    return key


def _write(client: Any, org_id: str, snoozes: dict[str, dict[str, Any]]) -> None:
    current = _read_settings(client, org_id)
    if current is None:
        raise SnoozeInputError("Your organization could not be found.")
    current[SNOOZE_KEY] = snoozes
    client.table("organizations").update({"settings": current}).eq("id", org_id).execute()


def snooze_forecast(
    client: Any,
    org_id: str,
    *,
    key: str,
    title: str,
    days: int,
    user_id: str,
    user_name: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    key = _clean_key(key)
    if days not in SNOOZE_DAYS:
        raise SnoozeInputError("Snooze for 1, 7 or 30 days.")
    now = now or _now()
    snoozes = active_snoozes(_read_settings(client, org_id), now)
    if key not in snoozes and len(snoozes) >= MAX_SNOOZES:
        raise SnoozeInputError("Too many forecasts are snoozed. Bring one back first.")
    until = (now + timedelta(days=days)).isoformat()
    snoozes[key] = {"until": until, "title": str(title or "")[:200], "by": user_id, "byName": user_name, "at": now.isoformat()}
    _write(client, org_id, snoozes)
    _audit(client, org_id, user_id, key, {"title": str(title or "")[:200], "days": days, "until": until})
    return {"key": key, "until": until, "title": snoozes[key]["title"], "by": user_name}


def unsnooze_forecast(client: Any, org_id: str, *, key: str, user_id: str, now: datetime | None = None) -> bool:
    key = _clean_key(key)
    snoozes = active_snoozes(_read_settings(client, org_id), now)
    if key not in snoozes:
        return False
    snoozes.pop(key)
    _write(client, org_id, snoozes)
    _audit(client, org_id, user_id, key, {"undone": True})
    return True


def _audit(client: Any, org_id: str, user_id: str, key: str, metadata: dict[str, Any]) -> None:
    from app.workflows.audit import write_audit_event

    write_audit_event(client, org_id, user_id, AUDIT_ACTION, "intelligence_forecast", key, metadata)
