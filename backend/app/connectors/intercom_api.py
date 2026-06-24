"""Intercom REST API client."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

INTERCOM_API_BASE = "https://api.intercom.io"
INTERCOM_VERSION = "2.11"
TIMEOUT_SEC = 30.0


class IntercomAPIError(Exception):
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
    url = f"{INTERCOM_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Intercom-Version": INTERCOM_VERSION,
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise IntercomAPIError(
            f"Intercom API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def ensure_intercom_session(
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
        conn = get_connector_by_type(client, org_id, "intercom", environment_name=environment_name)
    if not conn:
        raise IntercomAPIError("No active Intercom connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="intercom",
        environment_name=environment_name,
    )
    if not token:
        raise IntercomAPIError(err or "Intercom OAuth not connected", status_code=401)
    return cid, token


def get_contact(access_token: str, contact_id: str) -> dict[str, Any]:
    data = _request("GET", f"/contacts/{contact_id}", access_token)
    return data if isinstance(data, dict) else {"contact": data}


def list_conversations(
    access_token: str,
    *,
    starting_after: str | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if starting_after:
        params["starting_after"] = starting_after
    if per_page is not None:
        params["per_page"] = per_page
    data = _request("GET", "/conversations", access_token, params=params or None)
    return data if isinstance(data, dict) else {"conversations": data}


def list_tickets(
    access_token: str,
    *,
    starting_after: str | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if starting_after:
        params["starting_after"] = starting_after
    if per_page is not None:
        params["per_page"] = per_page
    data = _request("GET", "/tickets", access_token, params=params or None)
    return data if isinstance(data, dict) else {"tickets": data}


def create_contact(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/contacts", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"contact": data}


def reply_to_conversation(
    access_token: str,
    conversation_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = _request("POST", f"/conversations/{conversation_id}/reply", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"conversation": data}


def create_ticket(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/tickets", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"ticket": data}


def apply_contact_tags(access_token: str, contact_id: str, tag_ids: list[str]) -> dict[str, Any]:
    data = _request(
        "POST",
        f"/contacts/{contact_id}/tags",
        access_token,
        json_body={"id": tag_ids[0]} if len(tag_ids) == 1 else {"ids": tag_ids},
    )
    return data if isinstance(data, dict) else {"tags": data}


def trigger_series_event(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/events", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"event": data}


def create_contact_note(
    access_token: str,
    contact_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    data = _request("POST", f"/contacts/{contact_id}/notes", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"note": data}


def search_contacts(access_token: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/contacts/search", access_token, json_body=payload)
    return data if isinstance(data, dict) else {"contacts": data}


def delete_contact(access_token: str, contact_id: str) -> dict[str, Any]:
    _request("DELETE", f"/contacts/{contact_id}", access_token)
    return {"contact_id": str(contact_id), "deleted": True}


def list_companies(
    access_token: str,
    *,
    page: int | None = None,
    per_page: int | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page
    data = _request("GET", "/companies", access_token, params=params or None)
    return data if isinstance(data, dict) else {"companies": data}
