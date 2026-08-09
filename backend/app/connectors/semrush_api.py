"""SEMrush Analytics API client (BYO API key).

Docs: https://developer.semrush.com/api/
- Domain / keyword reports: https://api.semrush.com/
- Backlinks reports: https://api.semrush.com/analytics/v1/
Auth: query param `key` (never a shared Gravitre key).
"""
from __future__ import annotations

import csv
import io
from typing import Any

import httpx

from app.config import Settings
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret

SEMRUSH_API_BASE = "https://api.semrush.com/"
SEMRUSH_ANALYTICS_V1 = "https://api.semrush.com/analytics/v1/"
SEMRUSH_PROJECTS_V1 = "https://api.semrush.com/apis/v4/projects/v1"
SEMRUSH_MANAGEMENT_V1 = "https://api.semrush.com/management/v1"
TIMEOUT_SEC = 45.0

DOMAIN_OVERVIEW_COLUMNS = "Db,Dn,Rk,Or,Ot,Oc,Ad,At,Ac,Sh,Sv"
DOMAIN_ORGANIC_COLUMNS = "Ph,Po,Pp,Pd,Nq,Cp,Ur,Tr,Tc,Co,Nr,Td"
BACKLINKS_COLUMNS = (
    "source_url,target_url,anchor,external_num,internal_num,nofollow,"
    "first_seen,last_seen,page_score"
)


class SemrushAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def resolve_semrush_connector(
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
        conn = get_connector_by_type(client, org_id, "semrush", environment_name=environment_name)
    if not conn:
        raise SemrushAPIError("No active SEMrush connector found", status_code=404)
    cid = str(conn["id"])
    api_key = get_decrypted_secret(client, cid, "api_token", settings) or get_decrypted_secret(
        client, cid, "api_key", settings
    )
    if not api_key:
        raise SemrushAPIError(
            "SEMrush API key not configured (BYO — connect your own key)",
            status_code=401,
        )
    return cid, api_key.strip()


def _parse_semrush_table(text: str) -> list[dict[str, str]]:
    raw = (text or "").strip()
    if not raw:
        return []
    # ERROR lines look like: ERROR 43 :: ERROR 43 :: API KEY ...
    upper = raw.upper()
    if upper.startswith("ERROR"):
        raise SemrushAPIError(raw.splitlines()[0][:500], status_code=400, details=raw)
    dialect = csv.excel
    sample = raw.splitlines()[0] if raw else ""
    delimiter = ";" if ";" in sample else ","
    reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter, dialect=dialect)
    rows: list[dict[str, str]] = []
    for row in reader:
        if not isinstance(row, dict):
            continue
        cleaned = {str(k).strip(): ("" if v is None else str(v).strip()) for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


def _get(
    url: str,
    *,
    api_key: str,
    params: dict[str, Any],
) -> list[dict[str, str]]:
    query = {"key": api_key, **{k: v for k, v in params.items() if v is not None}}
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.get(url, params=query)
    body = response.text or ""
    if response.status_code >= 400:
        raise SemrushAPIError(
            body[:500] or f"SEMrush API error {response.status_code}",
            status_code=response.status_code,
            details=body,
        )
    return _parse_semrush_table(body)


def domain_overview(
    api_key: str,
    *,
    domain: str,
    database: str = "us",
) -> dict[str, Any]:
    domain = str(domain or "").strip().lower()
    if not domain:
        raise SemrushAPIError("domain is required", status_code=400)
    rows = _get(
        SEMRUSH_API_BASE,
        api_key=api_key,
        params={
            "type": "domain_ranks",
            "domain": domain,
            "database": database or "us",
            "export_columns": DOMAIN_OVERVIEW_COLUMNS,
        },
    )
    return {"domain": domain, "database": database or "us", "rows": rows, "row_count": len(rows)}


def keywords_list(
    api_key: str,
    *,
    domain: str,
    database: str = "us",
    limit: int = 20,
) -> dict[str, Any]:
    domain = str(domain or "").strip().lower()
    if not domain:
        raise SemrushAPIError("domain is required", status_code=400)
    display_limit = max(1, min(int(limit or 20), 100))
    rows = _get(
        SEMRUSH_API_BASE,
        api_key=api_key,
        params={
            "type": "domain_organic",
            "domain": domain,
            "database": database or "us",
            "display_limit": display_limit,
            "display_sort": "tr_desc",
            "export_columns": DOMAIN_ORGANIC_COLUMNS,
        },
    )
    return {
        "domain": domain,
        "database": database or "us",
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
    }


def backlinks_list(
    api_key: str,
    *,
    target: str,
    target_type: str = "root_domain",
    limit: int = 20,
) -> dict[str, Any]:
    target = str(target or "").strip().lower()
    if not target:
        raise SemrushAPIError("target is required", status_code=400)
    display_limit = max(1, min(int(limit or 20), 100))
    tt = str(target_type or "root_domain").strip().lower()
    if tt not in {"root_domain", "domain", "url"}:
        tt = "root_domain"
    rows = _get(
        SEMRUSH_ANALYTICS_V1,
        api_key=api_key,
        params={
            "type": "backlinks",
            "target": target,
            "target_type": tt,
            "display_limit": display_limit,
            "export_columns": BACKLINKS_COLUMNS,
        },
    )
    return {
        "target": target,
        "target_type": tt,
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
    }


def _projects_request(
    api_key: str,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    url = f"{SEMRUSH_PROJECTS_V1}{path}"
    headers = {
        "Authorization": f"Apikey {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.request(method, url, headers=headers, json=json_body, params=params)
    body = response.text or ""
    if response.status_code >= 400:
        raise SemrushAPIError(
            body[:500] or f"SEMrush Projects API error {response.status_code}",
            status_code=response.status_code,
            details=body,
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except Exception:  # noqa: BLE001
        return {"raw": body}


def create_project(
    api_key: str,
    *,
    name: str,
    url: str | None = None,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_name = str(name or "").strip()
    if not project_name and isinstance(properties, dict):
        project_name = str(properties.get("name") or properties.get("project_name") or "").strip()
    if not project_name:
        raise SemrushAPIError("project name is required", status_code=400)
    body: dict[str, Any] = {"project_name": project_name}
    project_url = str(url or (properties or {}).get("url") or (properties or {}).get("project_url") or "").strip()
    if project_url:
        body["url"] = project_url
    data = _projects_request(api_key, "POST", "/projects", json_body=body)
    return {"project_name": project_name, "url": project_url or None, "data": data}


def add_position_tracking_keywords(
    api_key: str,
    *,
    project_id: str,
    keywords: list[Any] | dict[str, Any],
) -> dict[str, Any]:
    pid = str(project_id or "").strip()
    if not pid:
        raise SemrushAPIError("project_id is required", status_code=400)
    if isinstance(keywords, dict):
        keyword_rows = keywords.get("keywords") if isinstance(keywords.get("keywords"), list) else [keywords]
    else:
        keyword_rows = list(keywords or [])
    normalized: list[dict[str, Any]] = []
    for item in keyword_rows:
        if isinstance(item, str) and item.strip():
            normalized.append({"keyword": item.strip()})
        elif isinstance(item, dict) and (item.get("keyword") or item.get("name")):
            normalized.append(
                {
                    "keyword": str(item.get("keyword") or item.get("name")).strip(),
                    **({k: v for k, v in item.items() if k not in {"keyword", "name"}}),
                }
            )
    if not normalized:
        raise SemrushAPIError("keywords list is required", status_code=400)
    url = f"{SEMRUSH_MANAGEMENT_V1}/projects/{pid}/keywords"
    with httpx.Client(timeout=TIMEOUT_SEC) as http:
        response = http.put(
            url,
            params={"key": api_key},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"keywords": normalized},
        )
    body = response.text or ""
    if response.status_code >= 400:
        raise SemrushAPIError(
            body[:500] or f"SEMrush position tracking error {response.status_code}",
            status_code=response.status_code,
            details=body,
        )
    try:
        data = response.json() if response.content else {}
    except Exception:  # noqa: BLE001
        data = {"raw": body}
    return {"project_id": pid, "keyword_count": len(normalized), "data": data}


def competitors_compare(
    api_key: str,
    *,
    domain: str,
    database: str = "us",
    limit: int = 10,
) -> dict[str, Any]:
    domain = str(domain or "").strip().lower()
    if not domain:
        raise SemrushAPIError("domain is required", status_code=400)
    display_limit = max(1, min(int(limit or 10), 50))
    rows = _get(
        SEMRUSH_API_BASE,
        api_key=api_key,
        params={
            "type": "domain_domains",
            "domain": domain,
            "database": database or "us",
            "display_limit": display_limit,
            "export_columns": "Dn,Cr,Np,Or,Ot,Oc,Ad",
        },
    )
    return {
        "domain": domain,
        "database": database or "us",
        "rows": rows,
        "row_count": len(rows),
        "limit": display_limit,
    }


def batch_domain(
    api_key: str,
    *,
    domains: list[str],
    database: str = "us",
) -> dict[str, Any]:
    cleaned = [str(d or "").strip().lower() for d in domains if str(d or "").strip()]
    if not cleaned:
        raise SemrushAPIError("domains list is required", status_code=400)
    results = []
    errors = []
    for domain in cleaned[:25]:
        try:
            results.append(domain_overview(api_key, domain=domain, database=database))
        except SemrushAPIError as exc:
            errors.append({"domain": domain, "error": str(exc), "status_code": exc.status_code})
    return {
        "database": database or "us",
        "requested": len(cleaned),
        "completed": len(results),
        "results": results,
        "errors": errors,
    }


def exports_run(
    api_key: str,
    *,
    domain: str,
    database: str = "us",
    report_type: str = "domain_organic",
    limit: int = 100,
) -> dict[str, Any]:
    """Sync Analytics export (no async SEMrush export job API)."""
    domain = str(domain or "").strip().lower()
    if not domain:
        raise SemrushAPIError("domain is required", status_code=400)
    rtype = str(report_type or "domain_organic").strip() or "domain_organic"
    if rtype in {"domain_organic", "keywords"}:
        payload = keywords_list(api_key, domain=domain, database=database, limit=limit)
    elif rtype in {"domain_ranks", "overview"}:
        payload = domain_overview(api_key, domain=domain, database=database)
    else:
        payload = keywords_list(api_key, domain=domain, database=database, limit=limit)
        rtype = "domain_organic"
    return {
        "export_mode": "sync_analytics",
        "report_type": rtype,
        "domain": domain,
        "database": database or "us",
        "payload": payload,
    }
