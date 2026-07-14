"""Google Search Console API client (sites + search analytics)."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

GSC_API_BASE = "https://www.googleapis.com/webmasters/v3"
TIMEOUT_SEC = 30.0


class GoogleSearchConsoleAPIError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.details = details


def list_gsc_sites(access_token: str) -> list[dict[str, Any]]:
    """List Search Console sites available to the connected Google account."""
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.get(f"{GSC_API_BASE}/sites", headers=headers)
        if response.status_code >= 400:
            raise GoogleSearchConsoleAPIError(
                f"Search Console sites.list {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
                details=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            )
        data = response.json() or {}
    sites: list[dict[str, Any]] = []
    for entry in data.get("siteEntry") or []:
        site_url = str(entry.get("siteUrl") or "").strip()
        if not site_url:
            continue
        sites.append(
            {
                "site_url": site_url,
                "permission_level": entry.get("permissionLevel"),
            }
        )
    return sites


def query_search_analytics(
    access_token: str,
    site_url: str,
    *,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    row_limit: int = 25,
    start_row: int = 0,
) -> dict[str, Any]:
    """POST searchAnalytics.query for a verified site.

    Prefer dimensions=['page'] for pack aggregates. dimensions including 'query'
    return raw query strings — those must not enter Memory/KG (governance stop-line).
    """
    from datetime import date, timedelta

    def _normalize_date(value: str, *, default_offset_days: int = 0) -> str:
        raw = str(value or "").strip()
        lowered = raw.lower()
        today = date.today()
        if lowered in {"today", ""}:
            return today.isoformat()
        if lowered == "yesterday":
            return (today - timedelta(days=1)).isoformat()
        if lowered.endswith("daysago") and lowered[:-7].isdigit():
            return (today - timedelta(days=int(lowered[:-7]))).isoformat()
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            return raw
        return (today - timedelta(days=default_offset_days)).isoformat()

    dims = list(dimensions or ["page"])
    start = _normalize_date(start_date, default_offset_days=7)
    end = _normalize_date(end_date, default_offset_days=0)
    encoded = quote(site_url, safe="")
    body: dict[str, Any] = {
        "startDate": start,
        "endDate": end,
        "dimensions": dims,
        "rowLimit": max(1, min(int(row_limit), 25000)),
        "startRow": max(0, int(start_row)),
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=TIMEOUT_SEC) as client:
        response = client.post(
            f"{GSC_API_BASE}/sites/{encoded}/searchAnalytics/query",
            headers=headers,
            json=body,
        )
        if response.status_code >= 400:
            raise GoogleSearchConsoleAPIError(
                f"Search Console searchAnalytics.query {response.status_code}: {response.text[:300]}",
                status_code=response.status_code,
                details=response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            )
        data = response.json() or {}

    rows_out: list[dict[str, Any]] = []
    for row in data.get("rows") or []:
        keys = list(row.get("keys") or [])
        item: dict[str, Any] = {
            "clicks": row.get("clicks"),
            "impressions": row.get("impressions"),
            "ctr": row.get("ctr"),
            "position": row.get("position"),
        }
        for idx, dim in enumerate(dims):
            if idx < len(keys):
                item[dim] = keys[idx]
        rows_out.append(item)

    return {
        "site_url": site_url,
        "start_date": start,
        "end_date": end,
        "dimensions": dims,
        "rows": rows_out,
        "responseAggregationType": data.get("responseAggregationType"),
        "result_url": f"https://search.google.com/search-console?resource_id={quote(site_url, safe='')}",
    }
