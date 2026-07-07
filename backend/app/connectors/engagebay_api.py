"""EngageBay REST API client (API key auth)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

ENGAGEBAY_API_BASE = "https://app.engagebay.com/dev/api"
TIMEOUT_SEC = 30.0


class EngageBayAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_engagebay_api_key(
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
        conn = get_connector_by_type(client, org_id, "engagebay", environment_name=environment_name)
    if not conn:
        raise EngageBayAPIError("No active EngageBay connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise EngageBayAPIError("EngageBay API key not configured", status_code=401)
    return cid, api_key.strip()


def _request(
    api_key: str,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{ENGAGEBAY_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        raise EngageBayAPIError(
            response.text or f"EngageBay API error {response.status_code}",
            status_code=response.status_code,
            details=response.text,
        )
    if not response.content:
        return {}
    return response.json()


def search_contacts(api_key: str, *, query: str | None = None, email: str | None = None, limit: int = 25) -> Any:
    params: dict[str, Any] = {"page_size": limit}
    if email:
        params["email"] = email
    elif query:
        params["q"] = query
    return _request(api_key, "GET", "/contacts", params=params)


def get_contact(api_key: str, *, contact_id: str | None = None, email: str | None = None) -> Any:
    if contact_id:
        return _request(api_key, "GET", f"/contacts/contact/{contact_id}")
    if email:
        return search_contacts(api_key, email=email, limit=1)
    raise EngageBayAPIError("contact_id or email required", status_code=400)


def create_contact(api_key: str, payload: dict[str, Any]) -> Any:
    return _request(api_key, "POST", "/contacts/contact/add", json_body=payload)


def update_contact(api_key: str, contact_id: str, payload: dict[str, Any]) -> Any:
    body = dict(payload)
    body["id"] = contact_id
    return _request(api_key, "PUT", f"/contacts/contact/{contact_id}", json_body=body)


def list_deals(api_key: str, *, limit: int = 25) -> Any:
    return _request(api_key, "GET", "/deals", params={"page_size": limit})


def create_task(api_key: str, payload: dict[str, Any]) -> Any:
    return _request(api_key, "POST", "/tasks", json_body=payload)
