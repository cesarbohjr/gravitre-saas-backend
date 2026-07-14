"""MSP gravitree sources — NVD + CISA KEV (graceful degrade)."""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.intelligence_packs.shared.auth_mode import get_auth_mode
from app.intelligence_packs.shared.cache import get_source_cache
from app.intelligence_packs.shared.schemas import SourceResult, ok_result, unavailable

logger = get_logger(__name__)


async def fetch_nvd_cve(cve_id: str, *, settings: Settings | None = None) -> SourceResult:
    vendor = "nvd"
    mode = get_auth_mode(vendor).value
    cfg = settings or get_settings()
    key = (os.environ.get("NVD_API_KEY") or getattr(cfg, "nvd_api_key", "") or "").strip()
    cid = (cve_id or "").strip().upper()
    if not cid:
        return unavailable(vendor, auth_mode=mode, error_code="NVD_CVE_REQUIRED", message="CVE id required")
    cache_key = f"nvd:{cid}"
    api_key_present = bool(key)
    cached = get_source_cache().get(cache_key)
    if cached is not None:
        return ok_result(
            vendor,
            auth_mode=mode,
            data=cached,
            provenance={"source": "nvd", "cached": True, "api_key_present": api_key_present},
        )

    base = (os.environ.get("NVD_BASE_URL") or getattr(cfg, "nvd_base_url", "") or "https://services.nvd.nist.gov/rest/json").rstrip("/")
    headers = {"apiKey": key} if key else {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{base}/cves/2.0", params={"cveId": cid}, headers=headers)
            if resp.status_code != 200:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="NVD_HTTP_ERROR",
                    message=f"NVD returned HTTP {resp.status_code}",
                )
            data = resp.json()
            get_source_cache().set(cache_key, data, ttl_seconds=3600)
            return ok_result(
                vendor,
                auth_mode=mode,
                data=data,
                provenance={
                    "source": "nvd",
                    "cve": cid,
                    "api_key_present": api_key_present,
                    "rate_limit_tier": "authenticated" if api_key_present else "public",
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.debug("nvd_fetch_failed cve=%s error=%s", cid, exc)
        return unavailable(vendor, auth_mode=mode, error_code="NVD_FETCH_FAILED", message="NVD request failed")


async def fetch_cisa_kev(*, settings: Settings | None = None) -> SourceResult:
    vendor = "cisa_kev"
    mode = get_auth_mode(vendor).value
    cfg = settings or get_settings()
    url = (
        os.environ.get("CISA_KEV_URL")
        or getattr(cfg, "cisa_kev_url", "")
        or "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
    )
    cache_key = "cisa_kev:feed"
    cached = get_source_cache().get(cache_key)
    if cached is not None:
        return ok_result(vendor, auth_mode=mode, data=cached, provenance={"source": "cisa_kev", "cached": True})
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return unavailable(
                    vendor,
                    auth_mode=mode,
                    error_code="CISA_KEV_HTTP_ERROR",
                    message=f"CISA KEV returned HTTP {resp.status_code}",
                )
            data: dict[str, Any] = resp.json()
            # Keep payload bounded for cache
            vulns = (data.get("vulnerabilities") or [])[:50]
            slim = {"count": len(data.get("vulnerabilities") or []), "sample": vulns}
            get_source_cache().set(cache_key, slim, ttl_seconds=86400)
            return ok_result(vendor, auth_mode=mode, data=slim, provenance={"source": "cisa_kev", "url": url})
    except Exception as exc:  # noqa: BLE001
        logger.debug("cisa_kev_fetch_failed error=%s", exc)
        return unavailable(
            vendor, auth_mode=mode, error_code="CISA_KEV_FETCH_FAILED", message="CISA KEV request failed"
        )
