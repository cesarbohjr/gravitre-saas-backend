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


def register_builtin_mappers_and_signals() -> None:
    """Idempotent bootstrap — FRED + NVD + World Bank as registrations only."""
    register_mapper("fred", map_fred)
    register_mapper("nvd", map_nvd)
    register_mapper("world_bank", map_world_bank)
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
