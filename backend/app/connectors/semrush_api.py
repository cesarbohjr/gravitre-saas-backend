"""SEMrush Analytics API client (BYO API key).

Docs: https://developer.semrush.com/api/
- Domain / keyword reports: https://api.semrush.com/
- Backlinks reports: https://api.semrush.com/analytics/v1/
Auth: query param `key` (never a shared Gravitree key).
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
