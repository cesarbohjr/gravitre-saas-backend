"""Finseo Customer API client (BYO API key).

Docs: https://www.finseo.ai/developers/api
Base: https://api.finseo.ai/v1
Auth: Authorization: Bearer {api_key}
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

FINSEO_API_BASE = "https://api.finseo.ai/v1"
FINSEO_APP_URL = "https://app.finseo.ai"
TIMEOUT_SEC = 45.0


class FinseoAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_finseo_connector(
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
        conn = get_connector_by_type(client, org_id, "finseo", environment_name=environment_name)
    if not conn:
        raise FinseoAPIError("No active Finseo connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise FinseoAPIError(
            "Finseo API key not configured (BYO — connect your own key)",
            status_code=401,
        )
    return cid, api_key.strip()


def _request(
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{FINSEO_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, params=params, json=json_body)
    body_text = response.text or ""
    if response.status_code >= 400:
        raise FinseoAPIError(
            body_text[:500] or f"Finseo API error {response.status_code}",
            status_code=response.status_code,
            details=body_text,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001
        raise FinseoAPIError("Invalid JSON from Finseo", status_code=502, details=body_text) from exc


def _unwrap_data(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def _require_project_id(project_id: str | None) -> str:
    pid = str(project_id or "").strip()
    if not pid:
        raise FinseoAPIError("project_id is required", status_code=400)
    return pid


def list_projects(api_key: str) -> dict[str, Any]:
    data = _request(api_key, "/projects")
    rows = _unwrap_data(data)
    if not isinstance(rows, list):
        rows = []
    return {
        "rows": rows,
        "row_count": len(rows),
        "result_url": FINSEO_APP_URL,
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def _resolve_project_id(
    api_key: str,
    *,
    project_id: str | None = None,
    domain: str | None = None,
) -> str:
    pid = str(project_id or "").strip()
    if pid:
        return pid
    domain_norm = str(domain or "").strip().lower().removeprefix("https://").removeprefix("http://")
    domain_norm = domain_norm.split("/")[0].removeprefix("www.")
    if not domain_norm:
        raise FinseoAPIError("project_id or domain is required", status_code=400)
    listed = list_projects(api_key)
    for row in listed.get("rows") or []:
        if not isinstance(row, dict):
            continue
        row_domain = str(row.get("domain") or "").strip().lower().removeprefix("www.")
        row_url = str(row.get("websiteUrl") or row.get("website_url") or "").strip().lower()
        if row_domain == domain_norm or domain_norm in row_url:
            found = str(row.get("id") or "").strip()
            if found:
                return found
    raise FinseoAPIError(f"No Finseo project found for domain {domain_norm}", status_code=404)


def metrics_overview(
    api_key: str,
    *,
    project_id: str | None = None,
    domain: str | None = None,
    timeframe: str = "30d",
) -> dict[str, Any]:
    pid = _resolve_project_id(api_key, project_id=project_id, domain=domain)
    data = _request(
        api_key,
        f"/projects/{pid}/metrics",
        params={"timeframe": timeframe or "30d"},
    )
    return {
        "project_id": pid,
        "domain": domain,
        "timeframe": timeframe or "30d",
        "data": _unwrap_data(data),
        "result_url": f"{FINSEO_APP_URL}/projects/{pid}",
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def prompts_list(api_key: str, *, project_id: str) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    data = _request(api_key, f"/projects/{pid}/prompts")
    rows = _unwrap_data(data)
    if isinstance(rows, dict):
        rows = rows.get("prompts") or rows.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    return {
        "project_id": pid,
        "rows": rows,
        "row_count": len(rows),
        "result_url": f"{FINSEO_APP_URL}/projects/{pid}",
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def prompts_track(
    api_key: str,
    *,
    project_id: str,
    prompts: list[str],
) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    prompt_list = [str(p).strip() for p in (prompts or []) if str(p).strip()]
    if not prompt_list:
        raise FinseoAPIError("prompts is required", status_code=400)
    created: list[Any] = []
    for prompt in prompt_list:
        data = _request(
            api_key,
            f"/projects/{pid}/prompts",
            method="POST",
            json_body={"prompt": prompt},
        )
        created.append(_unwrap_data(data) if _unwrap_data(data) is not None else data)
    return {
        "project_id": pid,
        "prompt_count": len(prompt_list),
        "created": created,
        "result_url": f"{FINSEO_APP_URL}/projects/{pid}",
    }


def competitors_compare(api_key: str, *, project_id: str, timeframe: str = "30d") -> dict[str, Any]:
    pid = _require_project_id(project_id)
    data = _request(
        api_key,
        f"/projects/{pid}/competitors",
        params={"timeframe": timeframe or "30d", "sortBy": "visibility", "limit": 20},
    )
    payload = _unwrap_data(data)
    rows = payload.get("competitors") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        rows = payload if isinstance(payload, list) else []
    return {
        "project_id": pid,
        "timeframe": timeframe or "30d",
        "rows": rows,
        "row_count": len(rows),
        "result_url": f"{FINSEO_APP_URL}/projects/{pid}",
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def exports_run(api_key: str, *, project_id: str) -> dict[str, Any]:
    pid = _require_project_id(project_id)
    data = _request(api_key, f"/projects/{pid}/export")
    return {
        "project_id": pid,
        "data": _unwrap_data(data),
        "result_url": f"{FINSEO_APP_URL}/projects/{pid}",
        "raw": data if isinstance(data, dict) else {"value": data},
    }
