"""Phase 1.5 — ONE write_external_entity_with_provenance for all pack sources."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.intelligence_packs.shared.normalize import NormalizedExternalRecord
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)


def write_external_entity_with_provenance(
    client: Any,
    *,
    org_id: str,
    record: NormalizedExternalRecord,
    source_cache_id: str | None = None,
) -> dict[str, Any]:
    """Upsert one external_entities row from a normalized record."""
    vendor = str(record.get("vendor") or "").strip().lower()
    entity_type = str(record.get("entity_type") or "external").strip() or "external"
    external_id = str(record.get("external_id") or "").strip()
    if not org_id or not vendor or not external_id:
        raise ValueError("org_id, vendor, and external_id are required")

    now = datetime.now(timezone.utc).isoformat()
    provenance = safe_normalize_stored_dict(record, key='provenance')
    provenance.setdefault("source", vendor)
    provenance.setdefault("written_via", "write_external_entity_with_provenance")
    provenance.setdefault("written_at", now)

    row = {
        "org_id": org_id,
        "vendor": vendor,
        "entity_type": entity_type,
        "external_id": external_id,
        "title": (record.get("title") or external_id)[:500],
        "payload": record.get("payload") or {},
        "provenance": provenance,
        "source_cache_id": source_cache_id,
        "updated_at": now,
    }

    try:
        existing = (
            client.table("external_entities")
            .select("id")
            .eq("org_id", org_id)
            .eq("vendor", vendor)
            .eq("entity_type", entity_type)
            .eq("external_id", external_id)
            .limit(1)
            .execute()
        )
        existing_rows = existing.data or []
        if existing_rows:
            eid = str(existing_rows[0]["id"])
            client.table("external_entities").update(row).eq("id", eid).execute()
            return {"id": eid, "created": False, "vendor": vendor, "external_id": external_id}
        eid = str(uuid4())
        row["id"] = eid
        row["created_at"] = now
        client.table("external_entities").insert(row).execute()
        return {"id": eid, "created": True, "vendor": vendor, "external_id": external_id}
    except Exception as exc:  # noqa: BLE001
        logger.warning("external_entity_write_failed vendor=%s err=%s", vendor, exc)
        raise
