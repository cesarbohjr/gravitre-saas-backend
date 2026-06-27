"""Canva Connect REST API client."""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.generic_oauth import ensure_generic_session
from app.connectors.repository import get_connector, get_connector_by_type

CANVA_API_BASE = "https://api.canva.com/rest/v1"
TIMEOUT_SEC = 30.0


class CanvaAPIError(Exception):
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
    url = f"{CANVA_API_BASE}{path}"
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
        raise CanvaAPIError(
            f"Canva API {response.status_code}",
            status_code=response.status_code,
            details=detail,
        )
    if not response.text:
        return {}
    return response.json()


def ensure_canva_session(
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
        conn = get_connector_by_type(client, org_id, "canva", environment_name=environment_name)
    if not conn:
        raise CanvaAPIError("No active Canva connector found", status_code=404)
    cid = str(conn["id"])
    token, err = ensure_generic_session(
        client,
        org_id,
        cid,
        settings,
        vendor="canva",
        environment_name=environment_name,
    )
    if not token:
        raise CanvaAPIError(err or "Canva OAuth not connected", status_code=401)
    return cid, token


def list_designs(
    access_token: str,
    *,
    query: str | None = None,
    continuation: str | None = None,
    ownership: str | None = None,
    sort_by: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if continuation:
        params["continuation"] = continuation
    if ownership:
        params["ownership"] = ownership
    if sort_by:
        params["sort_by"] = sort_by
    data = _request("GET", "/designs", access_token, params=params or None)
    return data if isinstance(data, dict) else {"items": data}


def get_design(access_token: str, design_id: str) -> dict[str, Any]:
    data = _request("GET", f"/designs/{design_id}", access_token)
    return data if isinstance(data, dict) else {"design": data}


def list_folder_items(
    access_token: str,
    folder_id: str,
    *,
    continuation: str | None = None,
    item_types: str | None = None,
    sort_by: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if continuation:
        params["continuation"] = continuation
    if item_types:
        params["item_types"] = item_types
    if sort_by:
        params["sort_by"] = sort_by
    data = _request("GET", f"/folders/{folder_id}/items", access_token, params=params or None)
    return data if isinstance(data, dict) else {"items": data}


def create_design(access_token: str, body: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/designs", access_token, json_body=body)
    return data if isinstance(data, dict) else {"design": data}


def delete_design(access_token: str, design_id: str) -> dict[str, Any]:
    data = _request("DELETE", f"/designs/{design_id}", access_token)
    return data if isinstance(data, dict) else {}


def create_export(access_token: str, body: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/exports", access_token, json_body=body)
    return data if isinstance(data, dict) else {"export": data}


def get_export(access_token: str, export_id: str) -> dict[str, Any]:
    data = _request("GET", f"/exports/{export_id}", access_token)
    return data if isinstance(data, dict) else {"export": data}


def create_autofill(access_token: str, body: dict[str, Any]) -> dict[str, Any]:
    data = _request("POST", "/autofills", access_token, json_body=body)
    return data if isinstance(data, dict) else {"job": data}


def list_brand_templates(
    access_token: str,
    *,
    query: str | None = None,
    continuation: str | None = None,
    dataset: str | None = None,
    ownership: str | None = None,
    sort_by: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if query:
        params["query"] = query
    if continuation:
        params["continuation"] = continuation
    if dataset:
        params["dataset"] = dataset
    if ownership:
        params["ownership"] = ownership
    if sort_by:
        params["sort_by"] = sort_by
    data = _request("GET", "/brand-templates", access_token, params=params or None)
    return data if isinstance(data, dict) else {"items": data}


def get_brand_template(access_token: str, brand_template_id: str) -> dict[str, Any]:
    data = _request("GET", f"/brand-templates/{brand_template_id}", access_token)
    return data if isinstance(data, dict) else {"brand_template": data}


def batch_exports(
    access_token: str,
    *,
    design_ids: list[str],
    format_type: str = "pdf",
    format_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    exports: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    fmt: dict[str, Any] = {"type": format_type}
    if format_options:
        fmt.update(format_options)
    for design_id in design_ids:
        try:
            result = create_export(
                access_token,
                {"design_id": str(design_id), "format": fmt},
            )
            exports.append({"design_id": str(design_id), "result": result})
        except CanvaAPIError as exc:
            errors.append({"design_id": str(design_id), "error": str(exc), "details": exc.details})
    return {"exports": exports, "errors": errors}
