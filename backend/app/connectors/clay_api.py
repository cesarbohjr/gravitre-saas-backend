"""Clay.com integration client (API key + table webhooks).

Clay is webhook-first for table ingestion and offers an Enterprise API for
people/company lookups. Workflow outputs are typically pushed from Clay via HTTP
API enrichment columns to external systems (CRM, etc.).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.core.safe_dict import safe_normalize_stored_dict

CLAY_API_BASE = "https://api.clay.com"
TIMEOUT_SEC = 30.0


class ClayAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def _connector_config(client: Any, org_id: str, connector_id: str) -> dict[str, Any]:
    row = (
        client.table("connectors")
        .select("config")
        .eq("org_id", org_id)
        .eq("id", connector_id)
        .limit(1)
        .execute()
    )
    return safe_normalize_stored_dict((row.data or [{}])[0], key="config")


def resolve_clay_connector(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "clay", environment_name=environment_name)
    if not conn:
        raise ClayAPIError("No active Clay connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise ClayAPIError("Clay API key not configured", status_code=401)
    config = safe_normalize_stored_dict(conn, key="config")
    if not config:
        config = _connector_config(client, org_id, cid)
    return cid, api_key.strip(), config


def resolve_clay_api_key(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str]:
    cid, api_key, _ = resolve_clay_connector(
        client, org_id, connector_id, settings, environment_name=environment_name
    )
    return cid, api_key


def _enterprise_request(
    api_key: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{CLAY_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, json=json_body)
    if response.status_code >= 400:
        raise ClayAPIError(
            response.text or f"Clay API error {response.status_code}",
            status_code=response.status_code,
            details=response.text,
        )
    if not response.content:
        return {}
    return response.json()


def verify_clay_api_key(api_key: str) -> bool:
    """Best-effort credential check using Enterprise people enrich."""
    try:
        enrich_person(api_key, email="verify@example.com")
        return True
    except ClayAPIError as exc:
        if exc.status_code in {401, 403}:
            return False
        # 402/404/422 often means key is valid but lookup failed — treat as connected.
        return exc.status_code not in {401, 403}


def list_tables(config: dict[str, Any]) -> dict[str, Any]:
    """Return configured Clay tables (webhook-backed; Clay has no public tables list API)."""
    tables = config.get("tables")
    if isinstance(tables, list) and tables:
        return {"tables": tables, "source": "connector_config"}
    webhook_url = str(config.get("webhook_url") or config.get("webhookUrl") or "").strip()
    if webhook_url:
        return {
            "tables": [
                {
                    "id": config.get("table_id") or config.get("tableId") or "default",
                    "name": config.get("table_name") or config.get("tableName") or "Default table",
                    "webhook_url": webhook_url,
                }
            ],
            "source": "connector_config",
        }
    return {"tables": [], "source": "connector_config", "note": "Configure tables or webhook_url on the connector."}


def enrich_person(
    api_key: str,
    *,
    email: str | None = None,
    linkedin_url: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = dict(payload or {})
    if email:
        body.setdefault("email", email)
    if linkedin_url:
        body.setdefault("linkedin_url", linkedin_url)
    if not body:
        raise ClayAPIError("email, linkedin_url, or payload required", status_code=400)
    return _enterprise_request(api_key, "POST", "/v1/people/enrich", json_body=body)


def enrich_company(
    api_key: str,
    *,
    domain: str | None = None,
    payload: dict[str, Any] | None = None,
) -> Any:
    body = dict(payload or {})
    if domain:
        body.setdefault("domain", domain)
    if not body:
        raise ClayAPIError("domain or payload required", status_code=400)
    return _enterprise_request(api_key, "POST", "/v1/companies/enrich", json_body=body)


def push_to_webhook(
    webhook_url: str,
    payload: dict[str, Any] | None = None,
    *,
    records: list[dict[str, Any]] | None = None,
    webhook_secret: str | None = None,
) -> Any:
    url = webhook_url.strip()
    if not url:
        raise ClayAPIError("Clay table webhook URL not configured", status_code=400)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret.strip()
    rows = records if records else ([payload] if payload else [])
    if not rows:
        raise ClayAPIError("payload or records required", status_code=400)
    results: list[dict[str, Any]] = []
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        for row in rows:
            response = http.post(url, headers=headers, json=row)
            if response.status_code >= 400:
                raise ClayAPIError(
                    response.text or f"Clay webhook error {response.status_code}",
                    status_code=response.status_code,
                    details=response.text,
                )
            results.append(
                {
                    "status_code": response.status_code,
                    "body": response.json() if response.content else {},
                }
            )
    if len(results) == 1:
        return {"submitted": 1, "result": results[0]}
    return {"submitted": len(results), "results": results}


def request_enrichment(
    api_key: str,
    config: dict[str, Any],
    *,
    records: list[dict[str, Any]],
    table_id: str | None = None,
    webhook_url: str | None = None,
) -> Any:
    """Push leads into Clay for table enrichment workflows."""
    url = (webhook_url or "").strip()
    if not url:
        tables = list_tables(config).get("tables") or []
        if table_id:
            match = next((t for t in tables if str(t.get("id")) == str(table_id)), None)
            url = str((match or {}).get("webhook_url") or "").strip()
        if not url and tables:
            url = str(tables[0].get("webhook_url") or "").strip()
        if not url:
            url = str(config.get("webhook_url") or config.get("webhookUrl") or "").strip()
    secret = str(config.get("webhook_secret") or config.get("webhookSecret") or "").strip() or None
    webhook_result = push_to_webhook(url, records=records, webhook_secret=secret)
    return {
        "webhook": webhook_result,
        "table_id": table_id,
        "records_sent": len(records),
        "enterprise_api_available": bool(api_key),
    }


def pull_workflow_outputs(config: dict[str, Any]) -> dict[str, Any]:
    """Return configured workflow output destinations (Clay pushes via HTTP API columns)."""
    outputs = config.get("workflow_outputs") or config.get("workflowOutputs")
    if isinstance(outputs, list):
        return {"outputs": outputs, "source": "connector_config"}
    crm_target = str(config.get("crm_sync_target") or config.get("crmSyncTarget") or "").strip()
    crm_connector_id = str(config.get("crm_connector_id") or config.get("crmConnectorId") or "").strip()
    if crm_target or crm_connector_id:
        return {
            "outputs": [
                {
                    "type": "crm_sync",
                    "crm": crm_target or None,
                    "connector_id": crm_connector_id or None,
                }
            ],
            "source": "connector_config",
        }
    return {
        "outputs": [],
        "note": "Clay workflow outputs are delivered via HTTP API enrichment columns. Configure workflow_outputs or crm_sync_target on the connector.",
    }
