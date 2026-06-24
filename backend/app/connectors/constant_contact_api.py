"""Constant Contact v3 API client."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

CC_API_BASE = "https://api.cc.email/v3"
TIMEOUT_SEC = 30.0


class ConstantContactAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{CC_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise ConstantContactAPIError(
            f"Constant Contact API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def ensure_constant_contact_session(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(
            client, org_id, "constant_contact", environment_name=environment_name
        )
    if not conn:
        raise ConstantContactAPIError("No active Constant Contact connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="constant_contact",
        environment_name=environment_name,
    )
    if not token:
        raise ConstantContactAPIError(err or "Constant Contact OAuth not connected", status_code=401)
    return cid, token


def list_contacts(
    access_token: str,
    *,
    limit: int | None = None,
    cursor: str | None = None,
    email: str | None = None,
    status: str | None = None,
    lists: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if cursor:
        params["cursor"] = cursor
    if email:
        params["email"] = email
    if status:
        params["status"] = status
    if lists:
        params["lists"] = lists
    data = _request("GET", "/contacts", access_token, params=params or None)
    return data if isinstance(data, dict) else {"contacts": data}


def get_contact(access_token: str, contact_id: str) -> dict[str, Any]:
    data = _request("GET", f"/contacts/{contact_id}", access_token)
    return data if isinstance(data, dict) else {"contact": data}


def list_email_campaigns(
    access_token: str,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if cursor:
        params["cursor"] = cursor
    data = _request("GET", "/emails", access_token, params=params or None)
    return data if isinstance(data, dict) else {"campaigns": data}


def create_contact(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/contacts", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"contact": data}


def update_contact(access_token: str, contact_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("PUT", f"/contacts/{contact_id}", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"contact": data}


def create_email_campaign(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/emails", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"campaign": data}


def add_list_memberships(
    access_token: str,
    *,
    source: dict[str, Any],
    list_ids: list[str],
) -> dict[str, Any]:
    data = _request(
        "POST",
        "/activities/add_list_memberships",
        access_token,
        json_body={"source": source, "list_ids": list_ids},
    )
    return data if isinstance(data, dict) else {"activity": data}


def apply_contact_tags(
    access_token: str,
    *,
    source: dict[str, Any],
    tag_ids: list[str],
    exclude: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"source": source, "tag_ids": tag_ids}
    if exclude:
        body["exclude"] = exclude
    data = _request("POST", "/activities/contacts_taggings_add", access_token, json_body=body)
    return data if isinstance(data, dict) else {"activity": data}


def schedule_email_campaign(
    access_token: str,
    campaign_activity_id: str,
    *,
    scheduled_date: str,
) -> dict[str, Any]:
    data = _request(
        "POST",
        f"/emails/activities/{campaign_activity_id}/schedules",
        access_token,
        json_body={"scheduled_date": scheduled_date},
    )
    return data if isinstance(data, dict) else {"schedule": data}


def list_contact_lists(
    access_token: str,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if cursor:
        params["cursor"] = cursor
    data = _request("GET", "/contact_lists", access_token, params=params or None)
    return data if isinstance(data, dict) else {"lists": data}


def list_segments(
    access_token: str,
    *,
    limit: int | None = None,
    cursor: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    if cursor:
        params["cursor"] = cursor
    data = _request("GET", "/segments", access_token, params=params or None)
    return data if isinstance(data, dict) else {"segments": data}


def delete_contact(access_token: str, contact_id: str) -> dict[str, Any]:
    _request("DELETE", f"/contacts/{contact_id}", access_token)
    return {"contact_id": str(contact_id), "deleted": True}
