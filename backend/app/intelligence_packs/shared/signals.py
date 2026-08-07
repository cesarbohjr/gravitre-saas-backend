"""Phase 1.5 — ONE PackSignalDefinition registration path."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.intelligence_packs.shared.normalize import NormalizedExternalRecord
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)


@dataclass(frozen=True)
class PackSignalDefinition:
    id: str
    vendor: str
    signal_type: str
    title: str
    detect: Callable[[NormalizedExternalRecord], dict[str, Any] | None]
    severity: str = "info"


_REGISTRY: dict[str, PackSignalDefinition] = {}


def register_signal(definition: PackSignalDefinition) -> None:
    """Register a signal definition (idempotent by id)."""
    key = str(definition.id or "").strip()
    if not key:
        raise ValueError("PackSignalDefinition.id required")
    _REGISTRY[key] = definition


def registered_signals() -> frozenset[str]:
    return frozenset(_REGISTRY.keys())


def list_signals_for_vendor(vendor: str) -> list[PackSignalDefinition]:
    v = str(vendor or "").strip().lower()
    return [d for d in _REGISTRY.values() if d.vendor == v]


def evaluate_pack_signals(record: NormalizedExternalRecord) -> list[dict[str, Any]]:
    """Run all registrations for the record's vendor through the shared path."""
    vendor = str(record.get("vendor") or "").strip().lower()
    hits: list[dict[str, Any]] = []
    for definition in list_signals_for_vendor(vendor):
        detected = definition.detect(record)
        if not detected:
            continue
        hits.append(
            {
                "signal_definition_id": definition.id,
                "vendor": definition.vendor,
                "signal_type": definition.signal_type,
                "title": str(detected.get("title") or definition.title),
                "severity": str(detected.get("severity") or definition.severity),
                "payload": detected.get("payload") or {},
                "provenance": {
                    **safe_normalize_stored_dict(record, key='provenance'),
                    "signal_definition_id": definition.id,
                    "evaluated_via": "evaluate_pack_signals",
                },
            }
        )
    return hits


def persist_external_signal(
    client: Any,
    *,
    org_id: str,
    hit: dict[str, Any],
    entity_id: str | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid4()),
        "org_id": org_id,
        "signal_definition_id": hit["signal_definition_id"],
        "vendor": hit["vendor"],
        "signal_type": hit["signal_type"],
        "title": hit["title"][:500],
        "severity": hit.get("severity") or "info",
        "entity_id": entity_id,
        "payload": hit.get("payload") or {},
        "provenance": hit.get("provenance") or {},
        "detected_at": now,
        "created_at": now,
    }
    try:
        client.table("external_signals").insert(row).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("external_signal_persist_failed def=%s err=%s", hit.get("signal_definition_id"), exc)
        raise
    return {"id": row["id"], "signal_definition_id": row["signal_definition_id"], "vendor": row["vendor"]}
