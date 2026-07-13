"""Executive / shared gravitree-managed source clients (graceful degrade)."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.intelligence_packs.shared.auth_mode import get_auth_mode, is_activation_allowed
from app.intelligence_packs.shared.cache import get_source_cache
from app.intelligence_packs.shared.schemas import SourceResult, ok_result, unavailable

logger = get_logger(__name__)


def _settings(settings: Settings | None) -> Settings:
    return settings or get_settings()


def _env(*names: str) -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


async def fetch_fred_series(
    series_id: str,
    *,
    settings: Settings | None = None,
) -> SourceResult:
    vendor = "fred"
    mode = get_auth_mode(vendor).value
    sid = (series_id or "GDP").strip() or "GDP"
    key = _env("FRED_API_KEY") or getattr(_settings(settings), "fred_api_key", "") or ""
    if not key:
        return unavailable(
            vendor,
            auth_mode=mode,
            error_code="GRAVITREE_SOURCE_UNAVAILABLE",
            message="FRED is not yet available",
        )
    cache_key = f"fred:{sid}"
    cached = get_source_cache().get(cache_key)
    if cached is not None:
        return ok_result(vendor, auth_mode=mode, data=cached, provenance={"source": "fred", "cached": True})

    base = _env("FRED_BASE_URL") or "https://api.stlouisfed.org/fred"
    url = f"{base.rstrip('/')}/series/observations"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                params={"series_id": sid, "api_key": key, "file_type": "json", "sort_order": "desc", "limit": 5},
            )
            if resp.status_code != 200:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="FRED_HTTP_ERROR",
                    message=f"FRED returned HTTP {resp.status_code}",
                )
            payload = resp.json()
            observations = payload.get("observations") or []
            get_source_cache().set(cache_key, observations, ttl_seconds=3600)
            return ok_result(
                vendor,
                auth_mode=mode,
                data=observations,
                provenance={"source": "fred", "series_id": sid, "url": url},
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("fred_fetch_failed series=%s error=%s", sid, exc)
        return unavailable(vendor, auth_mode=mode, error_code="FRED_FETCH_FAILED", message="FRED request failed")


async def fetch_sec_company_filings(
    query: str,
    *,
    settings: Settings | None = None,
) -> SourceResult:
    vendor = "sec_edgar"
    mode = get_auth_mode(vendor).value
    user_agent = (
        _env("SEC_USER_AGENT")
        or getattr(_settings(settings), "sec_user_agent", "")
        or ""
    ).strip()
    if not user_agent or "@" not in user_agent:
        return unavailable(
            vendor,
            auth_mode=mode,
            error_code="SEC_USER_AGENT_REQUIRED",
            message="SEC_USER_AGENT must identify Gravitre and a contact email",
        )
    q = (query or "").strip()[:120]
    if not q:
        return unavailable(vendor, auth_mode=mode, error_code="SEC_QUERY_REQUIRED", message="Query required")

    cache_key = f"sec:{q.lower()}"
    cached = get_source_cache().get(cache_key)
    if cached is not None:
        return ok_result(vendor, auth_mode=mode, data=cached, provenance={"source": "sec_edgar", "cached": True})

    base = _env("SEC_BASE_URL") or "https://efts.sec.gov/LATEST"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base.rstrip('/')}/search-index",
                params={"q": q, "dateRange": "custom", "startdt": "2020-01-01", "forms": "10-K,10-Q,8-K"},
                headers={"User-Agent": user_agent},
            )
            if resp.status_code != 200:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="SEC_HTTP_ERROR",
                    message=f"SEC returned HTTP {resp.status_code}",
                )
            data = resp.json()
            hits = ((data.get("hits") or {}).get("hits") or [])[:5]
            findings: list[dict[str, Any]] = []
            for hit in hits:
                source = hit.get("_source") or {}
                findings.append(
                    {
                        "title": str(source.get("display_names") or source.get("entity_name") or q)[:240],
                        "form": str(source.get("form_type") or ""),
                        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={quote(q)}",
                    }
                )
            get_source_cache().set(cache_key, findings, ttl_seconds=1800)
            return ok_result(
                vendor,
                auth_mode=mode,
                data=findings,
                provenance={"source": "sec_edgar", "user_agent_set": True, "query": q},
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("sec_fetch_failed query=%s error=%s", q, exc)
        return unavailable(vendor, auth_mode=mode, error_code="SEC_FETCH_FAILED", message="SEC request failed")


async def fetch_world_bank_indicator(
    country_code: str = "US",
    indicator: str = "NY.GDP.MKTP.CD",
    *,
    settings: Settings | None = None,
) -> SourceResult:
    _ = settings
    vendor = "world_bank"
    mode = get_auth_mode(vendor).value
    cc = (country_code or "US").strip().upper()
    ind = (indicator or "NY.GDP.MKTP.CD").strip()
    cache_key = f"wb:{cc}:{ind}"
    cached = get_source_cache().get(cache_key)
    if cached is not None:
        return ok_result(vendor, auth_mode=mode, data=cached, provenance={"source": "world_bank", "cached": True})

    base = _env("WORLDBANK_BASE_URL") or "https://api.worldbank.org/v2"
    url = f"{base.rstrip('/')}/country/{cc}/indicator/{ind}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params={"format": "json", "per_page": 5})
            if resp.status_code != 200:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="WORLD_BANK_HTTP_ERROR",
                    message=f"World Bank returned HTTP {resp.status_code}",
                )
            payload = resp.json()
            rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
            get_source_cache().set(cache_key, rows or [], ttl_seconds=86400)
            return ok_result(
                vendor,
                auth_mode=mode,
                data=rows or [],
                provenance={"source": "world_bank", "country": cc, "indicator": ind},
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("world_bank_fetch_failed error=%s", exc)
        return unavailable(
            vendor, auth_mode=mode, error_code="WORLD_BANK_FETCH_FAILED", message="World Bank request failed"
        )


async def fetch_oecd_dataset(
    dataset: str = "MEI",
    *,
    settings: Settings | None = None,
) -> SourceResult:
    _ = settings
    vendor = "oecd"
    mode = get_auth_mode(vendor).value
    ds = (dataset or "MEI").strip()
    cache_key = f"oecd:{ds}"
    cached = get_source_cache().get(cache_key)
    if cached is not None:
        return ok_result(vendor, auth_mode=mode, data=cached, provenance={"source": "oecd", "cached": True})

    base = _env("OECD_BASE_URL") or "https://sdmx.oecd.org/public/rest/data"
    # Lightweight ping â€” OECD SDMX can be heavy; return structured availability probe.
    url = f"{base.rstrip('/')}/{ds}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.status_code >= 500:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="OECD_HTTP_ERROR",
                    message=f"OECD returned HTTP {resp.status_code}",
                )
            # 404/400 still "reachable" â€” surface as empty with ok for capability probe
            data: dict[str, Any] = {
                "dataset": ds,
                "http_status": resp.status_code,
                "bytes": len(resp.content or b""),
            }
            get_source_cache().set(cache_key, data, ttl_seconds=3600)
            return ok_result(vendor, auth_mode=mode, data=data, provenance={"source": "oecd", "dataset": ds})
    except Exception as exc:  # noqa: BLE001
        logger.debug("oecd_fetch_failed error=%s", exc)
        return unavailable(vendor, auth_mode=mode, error_code="OECD_FETCH_FAILED", message="OECD request failed")


async def fetch_opencorporates_search(
    query: str,
    *,
    jurisdiction_code: str | None = None,
    settings: Settings | None = None,
) -> SourceResult:
    """Built but activation-gated until commercial license is confirmed."""
    vendor = "opencorporates"
    mode = get_auth_mode(vendor).value
    cfg = _settings(settings)
    if not is_activation_allowed(vendor, settings=cfg):
        return unavailable(
            vendor,
            auth_mode=mode,
            error_code="SOURCE_ACTIVATION_BLOCKED",
            message="OpenCorporates awaits commercial-license confirmation (code ready, not enabled)",
        )
    token = _env("OPENCORPORATES_API_TOKEN") or getattr(cfg, "opencorporates_api_token", "") or ""
    if not token:
        return unavailable(
            vendor,
            auth_mode=mode,
            error_code="GRAVITREE_SOURCE_UNAVAILABLE",
            message="OpenCorporates is not yet available",
        )
    q = (query or "").strip()
    if not q:
        return unavailable(vendor, auth_mode=mode, error_code="OC_QUERY_REQUIRED", message="Query required")

    base = _env("OPENCORPORATES_BASE_URL") or "https://api.opencorporates.com"
    params: dict[str, Any] = {"q": q, "api_token": token, "normalise_company_name": "true"}
    if jurisdiction_code:
        params["jurisdiction_code"] = jurisdiction_code
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(f"{base.rstrip('/')}/v0.4/companies/search", params=params)
            if resp.status_code != 200:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="OC_HTTP_ERROR",
                    message=f"OpenCorporates returned HTTP {resp.status_code}",
                )
            companies = ((resp.json().get("results") or {}).get("companies") or [])[:10]
            return ok_result(
                vendor,
                auth_mode=mode,
                data=companies,
                provenance={"source": "opencorporates", "api_version": "0.4"},
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("opencorporates_fetch_failed error=%s", exc)
        return unavailable(
            vendor, auth_mode=mode, error_code="OC_FETCH_FAILED", message="OpenCorporates request failed"
        )
