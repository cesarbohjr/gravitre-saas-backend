"""PagerDuty REST API v2 client (STA-38)."""
from __future__ import annotations

import time
from typing import Any

import httpx

PAGERDUTY_API_BASE = "https://api.pagerduty.com"
TIMEOUT_SEC = 30.0
MAX_RETRIES = 2
RETRY_BACKOFF_SEC = 1.0


class PagerDutyAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def api_request(
    method: str,
    path: str,
    access_token: str,
    *,
    json_body: dict[str, Any] | None = None,
    from_email: str | None = None,
) -> dict[str, Any]:
    url = f"{PAGERDUTY_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
    }
    if from_email:
        headers["From"] = from_email

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=TIMEOUT_SEC) as client:
                response = client.request(method, url, headers=headers, json=json_body)
            if response.status_code in {429, 500, 502, 503} and attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            if response.status_code >= 400:
                detail: Any = None
                try:
                    detail = response.json()
                except Exception:
                    detail = response.text[:500]
                raise PagerDutyAPIError(
                    f"PagerDuty API {response.status_code}: {path}",
                    status_code=response.status_code,
                    details=detail,
                )
            if response.status_code == 204 or not response.text:
                return {}
            data = response.json()
            return data if isinstance(data, dict) else {"data": data}
        except PagerDutyAPIError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise PagerDutyAPIError("PagerDuty API timeout") from exc
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * (attempt + 1))
                continue
            raise PagerDutyAPIError(str(exc)) from exc
    raise PagerDutyAPIError(str(last_error or "PagerDuty request failed"))


def fetch_current_user(access_token: str) -> dict[str, Any]:
    data = api_request("GET", "/users/me", access_token)
    return dict(data.get("user") or data)


def get_incident(access_token: str, incident_id: str) -> dict[str, Any]:
    data = api_request("GET", f"/incidents/{incident_id}", access_token)
    return dict(data.get("incident") or data)


def manage_incidents(
    access_token: str,
    incidents: list[dict[str, Any]],
    *,
    from_email: str,
) -> dict[str, Any]:
    payload = {
        "incidents": [
            {**item, "type": item.get("type") or "incident_reference"} for item in incidents
        ]
    }
    return api_request("PUT", "/incidents", access_token, json_body=payload, from_email=from_email)


def acknowledge_incident(
    access_token: str,
    incident_id: str,
    *,
    from_email: str,
) -> dict[str, Any]:
    return manage_incidents(
        access_token,
        [{"id": incident_id, "status": "acknowledged"}],
        from_email=from_email,
    )


def add_incident_note(
    access_token: str,
    incident_id: str,
    content: str,
    *,
    from_email: str,
) -> dict[str, Any]:
    return api_request(
        "POST",
        f"/incidents/{incident_id}/notes",
        access_token,
        json_body={"note": {"content": content}},
        from_email=from_email,
    )


def escalate_incident(
    access_token: str,
    incident_id: str,
    *,
    from_email: str,
    escalation_level: int | None = None,
) -> dict[str, Any]:
    level = escalation_level
    if level is None:
        current = get_incident(access_token, incident_id)
        existing = current.get("escalation_level")
        try:
            level = int(existing) + 1 if existing is not None else 1
        except (TypeError, ValueError):
            level = 1
    return manage_incidents(
        access_token,
        [{"id": incident_id, "escalation_level": int(level)}],
        from_email=from_email,
    )
