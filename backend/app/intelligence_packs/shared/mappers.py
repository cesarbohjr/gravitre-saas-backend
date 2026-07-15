"""Vendor mappers — plug into normalize_source_result; no parallel normalize stacks."""
from __future__ import annotations

from typing import Any

from app.intelligence_packs.shared.normalize import NormalizedExternalRecord, register_mapper
from app.intelligence_packs.shared.schemas import SourceResult
from app.intelligence_packs.shared.signals import PackSignalDefinition, register_signal


def map_fred(raw: SourceResult) -> list[NormalizedExternalRecord]:
    data = raw.get("data")
    observations: list[dict[str, Any]] = data if isinstance(data, list) else []
    prov = dict(raw.get("provenance") or {})
    series_id = str(prov.get("series_id") or "unknown")
    latest = next((o for o in observations if o.get("value") not in (None, ".", "")), None)
    title = f"FRED series {series_id}"
    if latest:
        title = f"FRED {series_id} @ {latest.get('date')} = {latest.get('value')}"
    return [
        {
            "vendor": "fred",
            "entity_type": "macro_series",
            "external_id": series_id,
            "title": title,
            "payload": {
                "series_id": series_id,
                "latest": latest,
                "observation_count": len(observations),
                "observations_sample": observations[:5],
            },
            "provenance": {**prov, "mapper": "map_fred"},
            "signal_hints": {"has_latest_value": latest is not None},
        }
    ]


def map_nvd(raw: SourceResult) -> list[NormalizedExternalRecord]:
    data = raw.get("data")
    payload = data if isinstance(data, dict) else {"raw": data}
    prov = dict(raw.get("provenance") or {})
    cve = str(prov.get("cve") or "").upper()
    vulns = payload.get("vulnerabilities") if isinstance(payload, dict) else None
    if not cve and isinstance(vulns, list) and vulns:
        cve_item = ((vulns[0] or {}).get("cve") or {})
        cve = str(cve_item.get("id") or "unknown").upper()
    if not cve:
        cve = "unknown"
    desc = ""
    if isinstance(vulns, list) and vulns:
        descs = ((vulns[0].get("cve") or {}).get("descriptions") or [])
        if descs:
            desc = str(descs[0].get("value") or "")[:240]
    return [
        {
            "vendor": "nvd",
            "entity_type": "cve",
            "external_id": cve,
            "title": desc or f"NVD {cve}",
            "payload": {
                "cve": cve,
                "vulnerability_count": len(vulns) if isinstance(vulns, list) else 0,
                "nvd": payload,
            },
            "provenance": {**prov, "mapper": "map_nvd"},
            "signal_hints": {"cve_found": isinstance(vulns, list) and len(vulns) > 0},
        }
    ]


def map_world_bank(raw: SourceResult) -> list[NormalizedExternalRecord]:
    """Third-source proof mapper — plugs into the same dispatcher only."""
    data = raw.get("data")
    rows: list[dict[str, Any]] = data if isinstance(data, list) else []
    prov = dict(raw.get("provenance") or {})
    country = str(prov.get("country") or "US")
    indicator = str(prov.get("indicator") or "unknown")
    latest = next((r for r in rows if r.get("value") is not None), None)
    external_id = f"{country}:{indicator}"
    title = f"World Bank {indicator} ({country})"
    if latest:
        title = f"{title} @ {latest.get('date')} = {latest.get('value')}"
    return [
        {
            "vendor": "world_bank",
            "entity_type": "indicator",
            "external_id": external_id,
            "title": title,
            "payload": {
                "country": country,
                "indicator": indicator,
                "latest": latest,
                "row_count": len(rows),
                "rows_sample": rows[:5],
            },
            "provenance": {**prov, "mapper": "map_world_bank"},
            "signal_hints": {"has_latest_value": latest is not None},
        }
    ]


def map_cisa_kev(raw: SourceResult) -> list[NormalizedExternalRecord]:
    data = raw.get("data")
    payload = data if isinstance(data, dict) else {"raw": data}
    prov = dict(raw.get("provenance") or {})
    sample = payload.get("sample") if isinstance(payload, dict) else None
    sample_list = sample if isinstance(sample, list) else []
    count = int(payload.get("count") or len(sample_list) or 0) if isinstance(payload, dict) else 0
    first = sample_list[0] if sample_list else {}
    cve = str((first or {}).get("cveID") or (first or {}).get("cveId") or "kev-feed").upper()
    title = str((first or {}).get("vulnerabilityName") or f"CISA KEV feed ({count} CVEs)")
    return [
        {
            "vendor": "cisa_kev",
            "entity_type": "kev_catalog",
            "external_id": "cisa-kev-feed",
            "title": title[:240],
            "payload": {
                "count": count,
                "sample_size": len(sample_list),
                "sample_cve": cve if cve != "KEV-FEED" else None,
                "kev": payload,
            },
            "provenance": {**prov, "mapper": "map_cisa_kev"},
            "signal_hints": {"kev_entries_present": count > 0},
        }
    ]


def map_sec_edgar(raw: SourceResult) -> list[NormalizedExternalRecord]:
    data = raw.get("data")
    findings: list[dict[str, Any]] = data if isinstance(data, list) else []
    prov = dict(raw.get("provenance") or {})
    query = str(prov.get("query") or "unknown")
    first = findings[0] if findings else {}
    title = str((first or {}).get("title") or f"SEC filings for {query}")
    return [
        {
            "vendor": "sec_edgar",
            "entity_type": "sec_filings",
            "external_id": f"sec:{query.lower()}",
            "title": title[:240],
            "payload": {
                "query": query,
                "filing_count": len(findings),
                "filings_sample": findings[:5],
            },
            "provenance": {**prov, "mapper": "map_sec_edgar"},
            "signal_hints": {"filings_found": len(findings) > 0},
        }
    ]


def map_google_search_console(raw: SourceResult) -> list[NormalizedExternalRecord]:
    """Map GSC searchAnalytics aggregates — never persist raw query strings."""
    from app.intelligence_packs.shared.gsc_data_governance import (
        assert_gsc_safe_for_memory_kg,
        sanitize_gsc_payload_for_memory_kg,
    )

    data = raw.get("data")
    payload = data if isinstance(data, dict) else {"raw": data}
    prov = dict(raw.get("provenance") or {})
    safe = sanitize_gsc_payload_for_memory_kg(payload)
    assert_gsc_safe_for_memory_kg(safe)
    rows = safe.get("rows") if isinstance(safe.get("rows"), list) else []
    site = str(
        safe.get("siteUrl")
        or safe.get("site_url")
        or prov.get("site_url")
        or prov.get("siteUrl")
        or "site"
    )
    total_clicks = 0
    total_impressions = 0
    page_sample: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        total_clicks += int(row.get("clicks") or 0)
        total_impressions += int(row.get("impressions") or 0)
        if len(page_sample) < 10:
            page_sample.append(
                {
                    "page": row.get("page") or row.get("keys"),
                    "clicks": row.get("clicks"),
                    "impressions": row.get("impressions"),
                    "position": row.get("position"),
                }
            )
    return [
        {
            "vendor": "google_search_console",
            "entity_type": "gsc_page_aggregates",
            "external_id": f"gsc:{site.lower()}:page",
            "title": f"GSC page aggregates ({len(rows)} rows)",
            "payload": {
                "site_url": site,
                "row_count": len(rows),
                "total_clicks": total_clicks,
                "total_impressions": total_impressions,
                "rows_sample": page_sample,
                "memoryKgEligible": True,
                "includes_raw_queries": False,
            },
            "provenance": {**prov, "mapper": "map_google_search_console"},
            "signal_hints": {
                "page_aggregates_present": bool(rows) or total_clicks > 0 or total_impressions > 0,
            },
        }
    ]


def _detect_fred_macro(record: NormalizedExternalRecord) -> dict[str, Any] | None:
    hints = record.get("signal_hints") or {}
    if not hints.get("has_latest_value"):
        return None
    latest = (record.get("payload") or {}).get("latest") or {}
    return {
        "title": record.get("title") or "FRED macro observation",
        "severity": "info",
        "payload": {"latest": latest, "series_id": (record.get("payload") or {}).get("series_id")},
    }


def _detect_nvd_cve(record: NormalizedExternalRecord) -> dict[str, Any] | None:
    hints = record.get("signal_hints") or {}
    if not hints.get("cve_found"):
        return None
    return {
        "title": record.get("title") or f"NVD CVE {record.get('external_id')}",
        "severity": "high",
        "payload": {"cve": record.get("external_id")},
    }


def _detect_world_bank_indicator(record: NormalizedExternalRecord) -> dict[str, Any] | None:
    hints = record.get("signal_hints") or {}
    if not hints.get("has_latest_value"):
        return None
    return {
        "title": record.get("title") or "World Bank indicator",
        "severity": "info",
        "payload": {"latest": (record.get("payload") or {}).get("latest")},
    }


def _detect_cisa_kev(record: NormalizedExternalRecord) -> dict[str, Any] | None:
    hints = record.get("signal_hints") or {}
    if not hints.get("kev_entries_present"):
        return None
    return {
        "title": record.get("title") or "CISA KEV catalog update",
        "severity": "high",
        "payload": {"count": (record.get("payload") or {}).get("count")},
    }


def _detect_sec_filings(record: NormalizedExternalRecord) -> dict[str, Any] | None:
    hints = record.get("signal_hints") or {}
    if not hints.get("filings_found"):
        return None
    return {
        "title": record.get("title") or "SEC EDGAR filings found",
        "severity": "info",
        "payload": {
            "query": (record.get("payload") or {}).get("query"),
            "filing_count": (record.get("payload") or {}).get("filing_count"),
        },
    }


def _detect_gsc_page_aggregates(record: NormalizedExternalRecord) -> dict[str, Any] | None:
    hints = record.get("signal_hints") or {}
    if not hints.get("page_aggregates_present"):
        return None
    payload = record.get("payload") or {}
    # Defense in depth — never emit query text into signal payloads
    from app.intelligence_packs.shared.gsc_data_governance import assert_gsc_safe_for_memory_kg

    assert_gsc_safe_for_memory_kg(payload)
    return {
        "title": record.get("title") or "GSC page performance rollup",
        "severity": "info",
        "payload": {
            "site_url": payload.get("site_url"),
            "row_count": payload.get("row_count"),
            "total_clicks": payload.get("total_clicks"),
            "total_impressions": payload.get("total_impressions"),
        },
    }


def register_builtin_mappers_and_signals() -> None:
    """Idempotent bootstrap — FRED + NVD + World Bank + CISA + SEC + GSC as registrations only."""
    register_mapper("fred", map_fred)
    register_mapper("nvd", map_nvd)
    register_mapper("world_bank", map_world_bank)
    register_mapper("cisa_kev", map_cisa_kev)
    register_mapper("sec_edgar", map_sec_edgar)
    register_mapper("google_search_console", map_google_search_console)
    register_signal(
        PackSignalDefinition(
            id="fred.macro_observation",
            vendor="fred",
            signal_type="macro_observation",
            title="FRED macro observation",
            detect=_detect_fred_macro,
        )
    )
    register_signal(
        PackSignalDefinition(
            id="nvd.cve_present",
            vendor="nvd",
            signal_type="cve_present",
            title="NVD CVE present",
            detect=_detect_nvd_cve,
            severity="high",
        )
    )
    register_signal(
        PackSignalDefinition(
            id="world_bank.indicator_observation",
            vendor="world_bank",
            signal_type="indicator_observation",
            title="World Bank indicator observation",
            detect=_detect_world_bank_indicator,
        )
    )
    register_signal(
        PackSignalDefinition(
            id="cisa_kev.catalog_present",
            vendor="cisa_kev",
            signal_type="kev_catalog_present",
            title="CISA KEV catalog present",
            detect=_detect_cisa_kev,
            severity="high",
        )
    )
    register_signal(
        PackSignalDefinition(
            id="sec_edgar.filings_present",
            vendor="sec_edgar",
            signal_type="sec_filings_present",
            title="SEC EDGAR filings present",
            detect=_detect_sec_filings,
        )
    )
    register_signal(
        PackSignalDefinition(
            id="gsc.page_performance_rollup",
            vendor="google_search_console",
            signal_type="gsc_page_performance",
            title="GSC page performance rollup",
            detect=_detect_gsc_page_aggregates,
        )
    )
