"""Phase 1.5 shared ingestion orchestration — uses ONE of each shared surface."""
from __future__ import annotations

from typing import Any

from app.intelligence_packs.shared.durable_cache import cache_get, cache_set
from app.intelligence_packs.shared.mappers import register_builtin_mappers_and_signals
from app.intelligence_packs.shared.normalize import normalize_source_result
from app.intelligence_packs.shared.provenance import write_external_entity_with_provenance
from app.intelligence_packs.shared.schemas import SourceResult
from app.intelligence_packs.shared.signals import evaluate_pack_signals, persist_external_signal

_BOOTSTRAPPED = False


def ensure_plumbing_registered() -> None:
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    register_builtin_mappers_and_signals()
    _BOOTSTRAPPED = True


def run_shared_ingestion(
    client: Any,
    *,
    org_id: str,
    vendor: str,
    cache_key: str,
    raw: SourceResult,
    ttl_seconds: int,
) -> dict[str, Any]:
    """cache_set → normalize_source_result → write_external_entity_with_provenance → signals."""
    ensure_plumbing_registered()
    v = str(vendor or raw.get("vendor") or "").strip().lower()
    if not raw.get("ok"):
        return {
            "ok": False,
            "vendor": v,
            "error_code": raw.get("error_code"),
            "message": raw.get("message"),
            "cache": None,
            "entities": [],
            "signals": [],
        }

    cache_row = cache_set(
        client,
        vendor=v,
        cache_key=cache_key,
        payload=raw.get("data"),
        ttl_seconds=ttl_seconds,
        provenance=dict(raw.get("provenance") or {}),
    )
    # Prove cache_get reads the same shared function
    cached = cache_get(client, vendor=v, cache_key=cache_key)

    records = normalize_source_result(v, raw)
    entities: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    for record in records:
        written = write_external_entity_with_provenance(
            client,
            org_id=org_id,
            record=record,
            source_cache_id=cache_row.get("id"),
        )
        entities.append(written)
        for hit in evaluate_pack_signals(record):
            persisted = persist_external_signal(
                client,
                org_id=org_id,
                hit=hit,
                entity_id=written.get("id"),
            )
            signals.append(persisted)

    return {
        "ok": True,
        "vendor": v,
        "cache": {
            "id": cache_row.get("id"),
            "cache_key": cache_key,
            "expires_at": cache_row.get("expires_at"),
            "round_trip_get_id": (cached or {}).get("id"),
        },
        "entities": entities,
        "signals": signals,
        "shared_surfaces": {
            "cache_get": "app.intelligence_packs.shared.durable_cache.cache_get",
            "cache_set": "app.intelligence_packs.shared.durable_cache.cache_set",
            "normalize_source_result": "app.intelligence_packs.shared.normalize.normalize_source_result",
            "write_external_entity_with_provenance": (
                "app.intelligence_packs.shared.provenance.write_external_entity_with_provenance"
            ),
            "pack_signal_registration": "app.intelligence_packs.shared.signals.register_signal",
        },
    }
