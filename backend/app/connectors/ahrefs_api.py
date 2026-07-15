"""Ahrefs API v3 client (BYO API key).

Docs: https://docs.ahrefs.com/docs/api/reference/introduction
Base: https://api.ahrefs.com/v3/
Auth: Authorization: Bearer {api_key}
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

AHREFS_API_BASE = "https://api.ahrefs.com/v3"
TIMEOUT_SEC = 45.0

ORGANIC_KEYWORDS_SELECT = "keyword,volume,best_position,keyword_difficulty,sum_traffic"
BACKLINKS_SELECT = "url_from,url_to,anchor,domain_rating_source,is_dofollow,first_seen"


class AhrefsAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_ahrefs_connector(
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
        conn = get_connector_by_type(client, org_id, "ahrefs", environment_name=environment_name)
    if not conn:
        raise AhrefsAPIError("No active Ahrefs connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise AhrefsAPIError(
            "Ahrefs API key not configured (BYO — connect your own key)",
            status_code=401,
        )
    return cid, api_key.strip()


def _default_report_date() -> str:
    # Ahrefs Site Explorer metrics lag a day; use yesterday UTC-ish calendar date.
    return (date.today() - timedelta(days=1)).isoformat()


def _request(
    api_key: str,
    path: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    url = f"{AHREFS_API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, params=params, json=json_body)
    body_text = response.text or ""
    if response.status_code >= 400:
        raise AhrefsAPIError(
            body_text[:500] or f"Ahrefs API error {response.status_code}",
            status_code=response.status_code,
            details=body_text,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception as exc:  # noqa: BLE001
        raise AhrefsAPIError("Invalid JSON from Ahrefs", status_code=502, details=body_text) from exc


def domain_rating(
    api_key: str,
    *,
    target: str,
    report_date: str | None = None,
) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    if not target:
        raise AhrefsAPIError("target is required", status_code=400)
    data = _request(
        api_key,
        "/site-explorer/domain-rating",
        params={"target": target, "date": report_date or _default_report_date()},
    )
    return {"target": target, "date": report_date or _default_report_date(), "data": data}


def keywords_list(
    api_key: str,
    *,
    target: str,
    country: str = "us",
    limit: int = 20,
    report_date: str | None = None,
) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    if not target:
        raise AhrefsAPIError("target is required", status_code=400)
    display_limit = max(1, min(int(limit or 20), 100))
    data = _request(
        api_key,
        "/site-explorer/organic-keywords",
        params={
            "target": target,
            "date": report_date or _default_report_date(),
            "country": (country or "us").lower(),
            "select": ORGANIC_KEYWORDS_SELECT,
            "limit": display_limit,
            "mode": "subdomains",
        },
    )
    rows = data.get("keywords") if isinstance(data, dict) else None
    if rows is None and isinstance(data, dict):
        rows = data.get("organic_keywords") or data.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    return {
        "target": target,
        "country": (country or "us").lower(),
        "date": report_date or _default_report_date(),
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def backlinks_list(
    api_key: str,
    *,
    target: str,
    limit: int = 20,
    mode: str = "subdomains",
) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    if not target:
        raise AhrefsAPIError("target is required", status_code=400)
    display_limit = max(1, min(int(limit or 20), 100))
    data = _request(
        api_key,
        "/site-explorer/all-backlinks",
        params={
            "target": target,
            "select": BACKLINKS_SELECT,
            "limit": display_limit,
            "mode": mode or "subdomains",
        },
    )
    rows = data.get("backlinks") if isinstance(data, dict) else None
    if rows is None and isinstance(data, dict):
        rows = data.get("rows") or []
    if not isinstance(rows, list):
        rows = []
    return {
        "target": target,
        "mode": mode or "subdomains",
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def create_project(
    api_key: str,
    *,
    name: str,
    url: str,
    protocol: str = "both",
    mode: str = "subdomains",
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_name = str(name or "").strip()
    if not project_name and isinstance(properties, dict):
        project_name = str(properties.get("name") or properties.get("project_name") or "").strip()
    target_url = str(url or (properties or {}).get("url") or "").strip()
    if not project_name:
        raise AhrefsAPIError("project name is required", status_code=400)
    if not target_url:
        raise AhrefsAPIError("url is required", status_code=400)
    body = {
        "project_name": project_name,
        "url": target_url,
        "protocol": protocol or "both",
        "mode": mode or "subdomains",
    }
    data = _request(api_key, "/management/projects", method="POST", json_body=body)
    return {"project_name": project_name, "url": target_url, "data": data}


def add_rank_tracker_keywords(
    api_key: str,
    *,
    project_id: str,
    keywords: list[Any] | dict[str, Any],
    locations: list[Any] | None = None,
) -> dict[str, Any]:
    pid = str(project_id or "").strip()
    if not pid:
        raise AhrefsAPIError("project_id is required", status_code=400)
    if isinstance(keywords, dict):
        keyword_rows = keywords.get("keywords") if isinstance(keywords.get("keywords"), list) else [keywords]
        if locations is None and isinstance(keywords.get("locations"), list):
            locations = keywords.get("locations")
    else:
        keyword_rows = list(keywords or [])
    normalized_keywords: list[str] = []
    for item in keyword_rows:
        if isinstance(item, str) and item.strip():
            normalized_keywords.append(item.strip())
        elif isinstance(item, dict) and (item.get("keyword") or item.get("name")):
            normalized_keywords.append(str(item.get("keyword") or item.get("name")).strip())
    if not normalized_keywords:
        raise AhrefsAPIError("keywords list is required", status_code=400)
    loc = locations if isinstance(locations, list) and locations else [{"country": "us"}]
    body = {"keywords": normalized_keywords, "locations": loc}
    data = _request(
        api_key,
        "/management/project-keywords",
        method="PUT",
        params={"project_id": pid},
        json_body=body,
    )
    return {
        "project_id": pid,
        "keyword_count": len(normalized_keywords),
        "locations": loc,
        "data": data,
    }


def competitors_compare(
    api_key: str,
    *,
    target: str,
    country: str = "us",
    limit: int = 10,
    report_date: str | None = None,
) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    if not target:
        raise AhrefsAPIError("target is required", status_code=400)
    display_limit = max(1, min(int(limit or 10), 50))
    data = _request(
        api_key,
        "/site-explorer/organic-competitors",
        params={
            "target": target,
            "date": report_date or _default_report_date(),
            "country": (country or "us").lower(),
            "select": "competitor,common_keywords,volume,traffic",
            "limit": display_limit,
        },
    )
    rows = data.get("competitors") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        rows = data.get("rows") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []
    return {
        "target": target,
        "country": (country or "us").lower(),
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
        "raw": data if isinstance(data, dict) else {"value": data},
    }


def top_pages_list(
    api_key: str,
    *,
    target: str,
    country: str = "us",
    limit: int = 20,
    report_date: str | None = None,
) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    if not target:
        raise AhrefsAPIError("target is required", status_code=400)
    display_limit = max(1, min(int(limit or 20), 100))
    data = _request(
        api_key,
        "/site-explorer/top-pages",
        params={
            "target": target,
            "date": report_date or _default_report_date(),
            "country": (country or "us").lower(),
            "select": "url,sum_traffic,keywords",
            "limit": display_limit,
        },
    )
    rows = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        rows = data.get("rows") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []
    return {
        "target": target,
        "country": (country or "us").lower(),
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
        "raw": data if isinstance(data, dict) else {"value": data},
    }
