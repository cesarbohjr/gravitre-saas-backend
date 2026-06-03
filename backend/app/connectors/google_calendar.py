"""Google Calendar API client (STA-23 stretch)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

CALENDAR_API = "https://www.googleapis.com/calendar/v3"
TIMEOUT_SEC = 30.0


class GoogleCalendarAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    access_token: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{CALENDAR_API}{path}"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, json=json_body, params=params)
    if response.status_code >= 400:
        detail: Any = None
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise GoogleCalendarAPIError(
            f"Google Calendar API {response.status_code}: {path}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def query_freebusy(
    access_token: str,
    *,
    calendar_id: str,
    time_min: str,
    time_max: str,
) -> dict[str, Any]:
    return _request(
        access_token,
        "POST",
        "/freeBusy",
        json_body={
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": calendar_id}],
        },
    )


def create_event(
    access_token: str,
    *,
    calendar_id: str = "primary",
    summary: str,
    description: str | None = None,
    start_iso: str,
    end_iso: str,
    attendees: list[str] | None = None,
    send_updates: str = "all",
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "summary": summary,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    if description:
        event["description"] = description
    if attendees:
        event["attendees"] = [{"email": email} for email in attendees]
    return _request(
        access_token,
        "POST",
        f"/calendars/{calendar_id}/events",
        json_body=event,
        params={"sendUpdates": send_updates},
    )


def default_window_iso(hours: int = 24) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    end = now.replace(microsecond=0)
    from datetime import timedelta

    start = end - timedelta(hours=hours)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")
