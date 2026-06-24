"""Odoo JSON-RPC client — API key authentication (SaaS + self-hosted).

Customers connect with Odoo URL, username, and an API key from Odoo Security settings.
No platform OAuth app or callback URL is required.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

TIMEOUT_SEC = 30.0


class OdooAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def normalize_odoo_url(raw: str) -> str:
    value = (raw or "").strip().rstrip("/")
    if not value:
        raise OdooAPIError("Odoo URL is required")
    if not value.startswith(("http://", "https://")):
        value = f"https://{value}"
    return value.rstrip("/")


def infer_database_name(base_url: str, explicit: str | None = None) -> str:
    db = (explicit or "").strip()
    if db:
        return db
    host = urlparse(base_url).hostname or ""
    if host.endswith(".odoo.com"):
        slug = host.removesuffix(".odoo.com").split(".")[-1]
        if slug:
            return slug
    raise OdooAPIError("Odoo database name is required for this instance")


def resolve_odoo_credentials(
    client: Any,
    org_id: str,
    connector_id: str | None,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> tuple[str, str, str, str, str]:
    conn = None
    if connector_id:
        conn = get_connector(client, org_id, connector_id, environment_name=environment_name)
    else:
        conn = get_connector_by_type(client, org_id, "odoo", environment_name=environment_name)
    if not conn:
        raise OdooAPIError("No active Odoo connector found for org")
    cid = str(conn["id"])
    config = conn.get("config") or {}
    base_url = normalize_odoo_url(
        str(config.get("odoo_url") or config.get("instance_url") or config.get("instanceUrl") or "")
    )
    database = infer_database_name(base_url, str(config.get("database") or config.get("db") or "") or None)
    username = get_decrypted_secret(client, cid, "username", settings) or get_decrypted_secret(
        client, cid, "login", settings
    )
    api_key = get_decrypted_secret(client, cid, "api_key", settings)
    if not username:
        raise OdooAPIError("Odoo username missing on connector", status_code=401)
    if not api_key:
        raise OdooAPIError("Odoo API key missing on connector", status_code=401)
    return cid, base_url, database, username.strip(), api_key.strip()


def _jsonrpc(base_url: str, service: str, method: str, args: list[Any]) -> Any:
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"service": service, "method": method, "args": args},
        "id": 1,
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.post(f"{base_url}/jsonrpc", json=payload)
    if response.status_code >= 400:
        raise OdooAPIError(
            f"Odoo JSON-RPC HTTP {response.status_code}",
            status_code=response.status_code,
            details=response.text[:500],
        )
    data = response.json()
    if data.get("error"):
        err = data["error"]
        message = err.get("message") or err.get("data", {}).get("message") or str(err)
        raise OdooAPIError(f"Odoo RPC error: {message}", details=err)
    return data.get("result")


def authenticate(base_url: str, database: str, username: str, api_key: str) -> int:
    uid = _jsonrpc(base_url, "common", "authenticate", [database, username, api_key, {}])
    if not uid:
        raise OdooAPIError("Odoo authentication failed — check URL, database, username, and API key", status_code=401)
    return int(uid)


def execute_kw(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    model: str,
    method: str,
    args: list[Any] | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Any:
    return _jsonrpc(
        base_url,
        "object",
        "execute_kw",
        [database, uid, api_key, model, method, args or [], kwargs or {}],
    )


def verify_odoo_credentials(base_url: str, database: str, username: str, api_key: str) -> int:
    return authenticate(base_url, database, username, api_key)


def get_partner(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    partner_id: int,
) -> dict[str, Any]:
    rows = execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "res.partner",
        "read",
        [[partner_id]],
        {"fields": ["id", "name", "email", "phone", "company_type"]},
    )
    if not rows:
        raise OdooAPIError(f"Partner {partner_id} not found", status_code=404)
    return rows[0]


def list_sale_orders(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "sale.order",
        "search_read",
        [[]],
        {
            "fields": ["id", "name", "partner_id", "amount_total", "state", "date_order"],
            "limit": max(1, min(limit, 200)),
        },
    )


def list_products(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "product.product",
        "search_read",
        [[]],
        {
            "fields": ["id", "name", "default_code", "list_price", "qty_available"],
            "limit": max(1, min(limit, 200)),
        },
    )


def _read_record(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    model: str,
    record_id: int,
    *,
    fields: list[str],
) -> dict[str, Any]:
    rows = execute_kw(
        base_url,
        database,
        uid,
        api_key,
        model,
        "read",
        [[record_id]],
        {"fields": fields},
    )
    if not rows:
        raise OdooAPIError(f"{model} {record_id} not found", status_code=404)
    return rows[0]


def create_partner(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    vals: dict[str, Any],
) -> dict[str, Any]:
    if not vals.get("name"):
        raise OdooAPIError("Partner name is required")
    partner_id = int(
        execute_kw(base_url, database, uid, api_key, "res.partner", "create", [vals])
    )
    return get_partner(base_url, database, uid, api_key, partner_id)


def update_partner(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    partner_id: int,
    vals: dict[str, Any],
) -> dict[str, Any]:
    if not vals:
        raise OdooAPIError("Partner update values are required")
    execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "res.partner",
        "write",
        [[partner_id], vals],
    )
    return get_partner(base_url, database, uid, api_key, partner_id)


def create_sale_order(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    vals: dict[str, Any],
) -> dict[str, Any]:
    if not vals.get("partner_id"):
        raise OdooAPIError("Sales order partner_id is required")
    order_id = int(execute_kw(base_url, database, uid, api_key, "sale.order", "create", [vals]))
    return _read_record(
        base_url,
        database,
        uid,
        api_key,
        "sale.order",
        order_id,
        fields=["id", "name", "partner_id", "amount_total", "state", "date_order"],
    )


def confirm_sale_order(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    order_id: int,
) -> dict[str, Any]:
    execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "sale.order",
        "action_confirm",
        [[order_id]],
    )
    return _read_record(
        base_url,
        database,
        uid,
        api_key,
        "sale.order",
        order_id,
        fields=["id", "name", "partner_id", "amount_total", "state", "date_order"],
    )


def create_invoice(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    vals: dict[str, Any],
) -> dict[str, Any]:
    payload = {**vals, "move_type": vals.get("move_type") or "out_invoice"}
    if not payload.get("partner_id"):
        raise OdooAPIError("Invoice partner_id is required")
    move_id = int(execute_kw(base_url, database, uid, api_key, "account.move", "create", [payload]))
    return _read_record(
        base_url,
        database,
        uid,
        api_key,
        "account.move",
        move_id,
        fields=["id", "name", "partner_id", "amount_total", "state", "move_type", "invoice_date"],
    )


def post_invoice(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    move_id: int,
) -> dict[str, Any]:
    execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "account.move",
        "action_post",
        [[move_id]],
    )
    return _read_record(
        base_url,
        database,
        uid,
        api_key,
        "account.move",
        move_id,
        fields=["id", "name", "partner_id", "amount_total", "state", "move_type", "invoice_date"],
    )


def create_manufacturing_order(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    vals: dict[str, Any],
) -> dict[str, Any]:
    if not vals.get("product_id"):
        raise OdooAPIError("Manufacturing order product_id is required")
    if vals.get("product_qty") is None and vals.get("product_uom_qty") is None:
        raise OdooAPIError("Manufacturing order product_qty is required")
    mo_id = int(execute_kw(base_url, database, uid, api_key, "mrp.production", "create", [vals]))
    return _read_record(
        base_url,
        database,
        uid,
        api_key,
        "mrp.production",
        mo_id,
        fields=["id", "name", "product_id", "product_qty", "state"],
    )


def convert_lead(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    lead_id: int,
    *,
    partner_id: int | None = None,
) -> dict[str, Any]:
    updates: dict[str, Any] = {"type": "opportunity"}
    if partner_id is not None:
        updates["partner_id"] = partner_id
    execute_kw(
        base_url,
        database,
        uid,
        api_key,
        "crm.lead",
        "write",
        [[lead_id], updates],
    )
    return _read_record(
        base_url,
        database,
        uid,
        api_key,
        "crm.lead",
        lead_id,
        fields=["id", "name", "type", "partner_id", "stage_id", "probability"],
    )


def batch_upsert_partners(
    base_url: str,
    database: str,
    uid: int,
    api_key: str,
    partners: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not partners:
        raise OdooAPIError("At least one partner record is required")
    results: list[dict[str, Any]] = []
    for item in partners:
        record_id = item.get("id") or item.get("partner_id") or item.get("partnerId")
        vals = {
            k: v
            for k, v in item.items()
            if k not in {"id", "partner_id", "partnerId"} and v is not None
        }
        if record_id is not None:
            results.append(update_partner(base_url, database, uid, api_key, int(record_id), vals))
        else:
            results.append(create_partner(base_url, database, uid, api_key, vals))
    return results


def odoo_connection_auth_status(
    client: Any,
    org_id: str,
    connector_id: str,
    settings: Settings,
    *,
    environment_name: str | None = None,
) -> str:
    try:
        _cid, base_url, database, username, api_key = resolve_odoo_credentials(
            client, org_id, connector_id, settings, environment_name=environment_name
        )
        verify_odoo_credentials(base_url, database, username, api_key)
        return "connected"
    except OdooAPIError as exc:
        if exc.status_code == 401:
            return "auth_expired"
        return "misconfigured"
    except Exception:
        return "misconfigured"
