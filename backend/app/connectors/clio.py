"""Clio Manage API v4 client — OAuth + demo sandbox (STA-114)."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

CLIO_API_BASE = "https://app.clio.com/api/v4"
TIMEOUT_SEC = 30.0

DEMO_CONTACTS: list[dict[str, Any]] = [
    {
        "id": 1001,
        "name": "Acme Holdings LLC",
        "type": "Company",
        "primary_email_address": "contact@acme.example",
        "primary_phone_number": "+1-555-0100",
    },
    {
        "id": 1002,
        "name": "Jane Rivera",
        "type": "Person",
        "primary_email_address": "jane.rivera@example.com",
        "primary_phone_number": "+1-555-0101",
    },
    {
        "id": 1003,
        "name": "Northwind Capital",
        "type": "Company",
        "primary_email_address": "ops@northwind.example",
        "primary_phone_number": "+1-555-0102",
    },
]

DEMO_MATTERS: list[dict[str, Any]] = [
    {
        "id": 2001,
        "display_number": "2024-001",
        "description": "Acme Holdings — contract dispute",
        "status": "Open",
        "client": {"id": 1001, "name": "Acme Holdings LLC"},
        "practice_area": "Litigation",
    },
    {
        "id": 2002,
        "display_number": "2024-014",
        "description": "Rivera estate planning",
        "status": "Open",
        "client": {"id": 1002, "name": "Jane Rivera"},
        "practice_area": "Trusts & Estates",
    },
    {
        "id": 2003,
        "display_number": "2023-088",
        "description": "Northwind Capital — acquisition diligence",
        "status": "Closed",
        "client": {"id": 1003, "name": "Northwind Capital"},
        "practice_area": "Corporate",
    },
]


class ClioAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _is_demo_connector(config: dict[str, Any]) -> bool:
    return bool(config.get("sandbox") or config.get("demo"))


def _request(
    method: str,
    path: str,
    access_token: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    url = f"{CLIO_API_BASE}/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise ClioAPIError(f"Clio API {response.status_code}", status_code=response.status_code, details=detail)
    if not response.text:
        return {}
    return response.json()


def ensure_clio_session(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str | None, bool]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "clio", environment_name=environment_name)
    if not conn:
        raise ClioAPIError("No active Clio connector found for org")
    cid = str(conn["id"])
    config = conn.get("config") or {}
    if _is_demo_connector(config):
        return cid, None, True
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="clio",
        environment_name=conn.get("environment") or environment_name,
    )
    if err or not token:
        raise ClioAPIError(err or "Clio OAuth not connected", status_code=401)
    return cid, token, False


def search_contacts(
    *,
    access_token: str | None,
    demo: bool,
    query: str | None = None,
    count: int = 10,
) -> dict[str, Any]:
    if demo:
        q = (query or "").strip().lower()
        rows = DEMO_CONTACTS
        if q:
            rows = [
                c
                for c in rows
                if q in str(c.get("name", "")).lower()
                or q in str(c.get("primary_email_address", "")).lower()
            ]
        return {"data": rows[: max(1, min(count, 50))], "meta": {"demo": True}}

    params: dict[str, Any] = {
        "fields": "id,name,type,primary_email_address,primary_phone_number",
        "limit": max(1, min(count, 50)),
    }
    if query:
        params["query"] = query
    return _request("GET", "contacts.json", access_token or "", params=params)


def get_contact(*, access_token: str | None, demo: bool, contact_id: str) -> dict[str, Any]:
    if demo:
        for row in DEMO_CONTACTS:
            if str(row["id"]) == str(contact_id):
                return {"data": row, "meta": {"demo": True}}
        raise ClioAPIError("Contact not found", status_code=404)

    return _request(
        "GET",
        f"contacts/{contact_id}.json",
        access_token or "",
        params={"fields": "id,name,type,primary_email_address,primary_phone_number"},
    )


def search_matters(
    *,
    access_token: str | None,
    demo: bool,
    query: str | None = None,
    client_id: str | None = None,
    count: int = 10,
) -> dict[str, Any]:
    if demo:
        q = (query or "").strip().lower()
        rows = DEMO_MATTERS
        if client_id:
            rows = [m for m in rows if str((m.get("client") or {}).get("id")) == str(client_id)]
        if q:
            rows = [
                m
                for m in rows
                if q in str(m.get("description", "")).lower()
                or q in str(m.get("display_number", "")).lower()
                or q in str((m.get("client") or {}).get("name", "")).lower()
            ]
        return {"data": rows[: max(1, min(count, 50))], "meta": {"demo": True}}

    params: dict[str, Any] = {
        "fields": "id,display_number,description,status,client,practice_area",
        "limit": max(1, min(count, 50)),
    }
    if query:
        params["query"] = query
    if client_id:
        params["client_id"] = client_id
    return _request("GET", "matters.json", access_token or "", params=params)
