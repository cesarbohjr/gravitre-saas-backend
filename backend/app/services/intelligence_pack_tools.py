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


def emit_pack_source_notification(
    ctx: ToolContext,
    *,
    title: str,
    body: str,
    result_url: str | None,
    action: str,
) -> None:
    """Phase 3.5 — pack source success through unified emit_notification path.

    Public so CRM/support executors (HubSpot/Zendesk) can reuse the same cohesion path.
    """
    actor = str(getattr(ctx, "actor_id", None) or "").strip()
    if not actor or not ctx.org_id:
        return
    try:
        from app.services.notification_emitter import emit_notification

        emit_notification(
            ctx.client,
            org_id=ctx.org_id,
            user_id=actor,
            event_type="task_completed",
            title=title,
            body=body,
            entity_ref={
                "type": "intelligence_pack_tool",
                "id": action,
                "result_url": result_url,
                "url": result_url,
            },
            channel_hints={"bell": True, "email": False},
        )
    except Exception:  # noqa: BLE001
        pass


# Back-compat alias for earlier Phase 3.5 call sites / tests
_emit_pack_source_notification = emit_pack_source_notification


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
    provenance = dict(raw.get("provenance") or {})
    result_url = str(provenance.get("url") or f"https://fred.stlouisfed.org/series/{series_id}")
    _emit_pack_source_notification(
        ctx,
        title=f"FRED series {series_id}",
        body=f"Fetched and ingested FRED series {series_id}.",
        result_url=result_url,
        action="fred.series.get",
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
            "result_url": result_url,
            "provenance": provenance,
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
    result_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"
    _emit_pack_source_notification(
        ctx,
        title=f"NVD {cve_id}",
        body=f"Fetched and ingested {cve_id}.",
        result_url=result_url,
        action="nvd.cve.get",
    )
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
            "result_url": result_url,
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
    from urllib.parse import quote

    ingested = run_shared_ingestion(
        ctx.client,
        org_id=ctx.org_id,
        vendor="sec_edgar",
        cache_key=f"filings:{query.lower()}",
        raw=raw,
        ttl_seconds=1800,
    )
    result_url = f"https://efts.sec.gov/LATEST/search-index?q={quote(query)}&dateRange=custom&startdt=2020-01-01"
    _emit_pack_source_notification(
        ctx,
        title=f"SEC EDGAR: {query}",
        body=f"Fetched and ingested SEC filings for {query}.",
        result_url=result_url,
        action="sec_edgar.filings.search",
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
            "result_url": result_url,
        },
    )


INTELLIGENCE_PACK_TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    "fred.series.get": _exec_fred_series_get,
    "nvd.cve.get": _exec_nvd_cve_get,
    "cisa_kev.feed.get": _exec_cisa_kev_feed_get,
    "sec_edgar.filings.search": _exec_sec_edgar_filings_search,
}
