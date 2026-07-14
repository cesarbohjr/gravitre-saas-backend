"""Phase 3 — gravitree-managed intelligence pack tool executors.

Thin wrappers over fetch_* + run_shared_ingestion. No parallel cache/normalize/KG stack.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import os
from typing import Any, Coroutine, TypeVar

from app.intelligence_packs.shared.auth_mode import AuthMode, get_auth_mode, resolve_credential_source
from app.intelligence_packs.shared.pipeline import run_shared_ingestion
from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

ToolExecutor = Any
T = TypeVar("T")


def _run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Run async fetch from sync invoke_tool executors."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _platform_key_present(vendor: str, settings: Any) -> bool:
    mode = get_auth_mode(vendor)
    if mode != AuthMode.GRAVITREE_MANAGED:
        return False
    if vendor == "fred":
        return bool(
            (os.environ.get("FRED_API_KEY") or getattr(settings, "fred_api_key", "") or "").strip()
        )
    if vendor == "nvd":
        # NVD allows unauthenticated reads; treat as available even without key
        return True
    if vendor == "cisa_kev":
        return True
    if vendor == "sec_edgar":
        ua = (os.environ.get("SEC_USER_AGENT") or getattr(settings, "sec_user_agent", "") or "").strip()
        return "@" in ua
    if vendor == "world_bank":
        return True
    return False


def _assert_gravitree_ready(vendor: str, ctx: ToolContext) -> None:
    present = _platform_key_present(vendor, ctx.settings)
    resolved = resolve_credential_source(
        vendor,
        org_has_secret=False,
        platform_env_present=present,
        settings=ctx.settings,
    )
    if not resolved.get("ok"):
        raise ToolValidationError(
            str(resolved.get("message") or f"{vendor} is not available"),
            code=str(resolved.get("error_code") or "GRAVITREE_SOURCE_UNAVAILABLE"),
        )


def _exec_fred_series_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.intelligence_packs.executive.sources import fetch_fred_series

    _assert_gravitree_ready("fred", ctx)
    series_id = str(params.get("series_id") or "GDP").strip() or "GDP"
    raw = _run_async(fetch_fred_series(series_id, settings=ctx.settings))
    if not raw.get("ok"):
        return NormalizedResult(
            success=False,
            action="fred.series.get",
            error_code=str(raw.get("error_code") or "FRED_FETCH_FAILED"),
            error_message=str(raw.get("message") or "FRED fetch failed"),
            connector_id=ctx.connector_id,
        )
    ingested = run_shared_ingestion(
        ctx.client,
        org_id=ctx.org_id,
        vendor="fred",
        cache_key=f"series:{series_id}",
        raw=raw,
        ttl_seconds=3600,
    )
    return NormalizedResult(
        success=True,
        action="fred.series.get",
        connector_id=ctx.connector_id,
        data={
            "vendor": "fred",
            "series_id": series_id,
            "observations": raw.get("data"),
            "ingestion": ingested,
        },
    )


def _exec_nvd_cve_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.intelligence_packs.msp import fetch_nvd_cve

    _assert_gravitree_ready("nvd", ctx)
    cve_id = str(params.get("cve_id") or "").strip().upper()
    if not cve_id:
        raise ToolValidationError("nvd.cve.get requires cve_id", code="NVD_CVE_REQUIRED")
    raw = _run_async(fetch_nvd_cve(cve_id, settings=ctx.settings))
    if not raw.get("ok"):
        return NormalizedResult(
            success=False,
            action="nvd.cve.get",
            error_code=str(raw.get("error_code") or "NVD_FETCH_FAILED"),
            error_message=str(raw.get("message") or "NVD fetch failed"),
            connector_id=ctx.connector_id,
        )
    ingested = run_shared_ingestion(
        ctx.client,
        org_id=ctx.org_id,
        vendor="nvd",
        cache_key=f"cve:{cve_id}",
        raw=raw,
        ttl_seconds=3600,
    )
    provenance = dict(raw.get("provenance") or {})
    return NormalizedResult(
        success=True,
        action="nvd.cve.get",
        connector_id=ctx.connector_id,
        data={
            "vendor": "nvd",
            "cve_id": cve_id,
            "nvd": raw.get("data"),
            "ingestion": ingested,
            "provenance": provenance,
            "api_key_present": bool(provenance.get("api_key_present")),
            "rate_limit_tier": provenance.get("rate_limit_tier")
            or ("authenticated" if provenance.get("api_key_present") else "public"),
        },
    )


def _exec_cisa_kev_feed_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.intelligence_packs.msp import fetch_cisa_kev

    _assert_gravitree_ready("cisa_kev", ctx)
    _ = params  # full feed sample; optional filters can follow
    raw = _run_async(fetch_cisa_kev(settings=ctx.settings))
    if not raw.get("ok"):
        return NormalizedResult(
            success=False,
            action="cisa_kev.feed.get",
            error_code=str(raw.get("error_code") or "CISA_KEV_FETCH_FAILED"),
            error_message=str(raw.get("message") or "CISA KEV fetch failed"),
            connector_id=ctx.connector_id,
        )
    ingested = run_shared_ingestion(
        ctx.client,
        org_id=ctx.org_id,
        vendor="cisa_kev",
        cache_key="feed:latest",
        raw=raw,
        ttl_seconds=86400,
    )
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    return NormalizedResult(
        success=True,
        action="cisa_kev.feed.get",
        connector_id=ctx.connector_id,
        data={
            "vendor": "cisa_kev",
            "count": data.get("count"),
            "sample": data.get("sample"),
            "ingestion": ingested,
        },
    )


def _exec_sec_edgar_filings_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.intelligence_packs.executive.sources import fetch_sec_company_filings

    _assert_gravitree_ready("sec_edgar", ctx)
    query = str(params.get("query") or params.get("company") or params.get("q") or "").strip()
    if not query:
        raise ToolValidationError(
            "sec_edgar.filings.search requires query",
            code="SEC_QUERY_REQUIRED",
        )
    raw = _run_async(fetch_sec_company_filings(query, settings=ctx.settings))
    if not raw.get("ok"):
        return NormalizedResult(
            success=False,
            action="sec_edgar.filings.search",
            error_code=str(raw.get("error_code") or "SEC_FETCH_FAILED"),
            error_message=str(raw.get("message") or "SEC EDGAR fetch failed"),
            connector_id=ctx.connector_id,
        )
    ingested = run_shared_ingestion(
        ctx.client,
        org_id=ctx.org_id,
        vendor="sec_edgar",
        cache_key=f"filings:{query.lower()}",
        raw=raw,
        ttl_seconds=1800,
    )
    return NormalizedResult(
        success=True,
        action="sec_edgar.filings.search",
        connector_id=ctx.connector_id,
        data={
            "vendor": "sec_edgar",
            "query": query,
            "filings": raw.get("data"),
            "ingestion": ingested,
        },
    )


INTELLIGENCE_PACK_TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    "fred.series.get": _exec_fred_series_get,
    "nvd.cve.get": _exec_nvd_cve_get,
    "cisa_kev.feed.get": _exec_cisa_kev_feed_get,
    "sec_edgar.filings.search": _exec_sec_edgar_filings_search,
}
