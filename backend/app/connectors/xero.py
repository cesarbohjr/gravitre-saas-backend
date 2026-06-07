"""Xero Accounting API client (STA-89)."""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

XERO_API_BASE = "https://api.xero.com/api.xro/2.0"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
TIMEOUT_SEC = 30.0


class XeroAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _request(
    method: str,
    url: str,
    access_token: str,
    *,
    tenant_id: str,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Xero-tenant-id": tenant_id,
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.request(method, url, headers=headers, params=params, json=json_body)
    if response.status_code >= 400:
        detail: Any
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:500]
        raise XeroAPIError(f"Xero API {response.status_code}", status_code=response.status_code, details=detail)
    if not response.text:
        return {}
    return response.json()


def fetch_connections(access_token: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(XERO_CONNECTIONS_URL, headers=headers)
    if response.status_code >= 400:
        raise XeroAPIError(f"Xero connections {response.status_code}", status_code=response.status_code)
    data = response.json()
    return data if isinstance(data, list) else []


def resolve_tenant_id(client: Any, org_id: str, connector_id: str, access_token: str) -> str:
    row = get_connector(client, org_id, connector_id)
    if not row:
        raise XeroAPIError("Connector not found", status_code=404)
    config = row.get("config") or {}
    tenant_id = (config.get("tenant_id") or config.get("xero_tenant_id") or "").strip()
    if tenant_id:
        return tenant_id
    connections = fetch_connections(access_token)
    if not connections:
        raise XeroAPIError("No Xero tenant connected to this authorization")
    tenant_id = str(connections[0].get("tenantId") or connections[0].get("tenant_id") or "")
    if not tenant_id:
        raise XeroAPIError("Xero tenant id missing from connections response")
    config = dict(config)
    config["tenant_id"] = tenant_id
    client.table("connectors").update({"config": config}).eq("id", connector_id).eq("org_id", org_id).execute()
    return tenant_id


def ensure_xero_session(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str, str]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "xero", environment_name=environment_name)
    if not conn:
        raise XeroAPIError("No active Xero connector found for org")
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="xero",
        environment_name=conn.get("environment") or environment_name,
    )
    if err or not token:
        raise XeroAPIError(err or "Xero OAuth not connected", status_code=401)
    tenant_id = resolve_tenant_id(client, org_id, cid, token)
    return cid, token, tenant_id


def list_contacts(access_token: str, tenant_id: str) -> dict[str, Any]:
    return _request("GET", f"{XERO_API_BASE}/Contacts", access_token, tenant_id=tenant_id)


def list_invoices(access_token: str, tenant_id: str) -> dict[str, Any]:
    return _request("GET", f"{XERO_API_BASE}/Invoices", access_token, tenant_id=tenant_id)


def list_accounts(access_token: str, tenant_id: str) -> dict[str, Any]:
    return _request("GET", f"{XERO_API_BASE}/Accounts", access_token, tenant_id=tenant_id)
