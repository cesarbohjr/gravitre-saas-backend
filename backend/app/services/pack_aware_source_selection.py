"""Pack-aware source selection for adaptive research cascade (Phase 3)."""
from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings
from app.core.logging import get_logger
from app.intelligence_packs.shared.kpis import PACK_VENDOR_MAP
from app.intelligence_packs.shared.sources import (
    PackSourceDefinition,
    ensure_pack_sources_registered,
    list_sources_for_pack,
)
from app.services.pack_operational_state_service import extract_pack_ids

logger = get_logger(__name__)

_MAX_PACK_ROWS = 8
_MAX_SIGNALS_PER_VENDOR = 3
_MAX_ENTITIES_PER_VENDOR = 2
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def should_run_pack_source_stage(
    research_scope: str | None,
    *,
    settings: Settings,
    knowledge_assignments: list[dict[str, Any]] | None,
) -> bool:
    """True when cascade includes intelligence_packs and the agent has pack assignments."""
    from app.services.adaptive_research_cascade import resolve_active_stages

    if "intelligence_packs" not in resolve_active_stages(research_scope, settings=settings):
        return False
    return bool(extract_pack_ids(knowledge_assignments))


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall(str(text or "").lower()) if len(token) > 2}


def score_source_relevance(source: PackSourceDefinition, query: str) -> float:
    """Lightweight keyword overlap — no ML scoring."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.35
    haystack = " ".join(
        [
            source.title,
            source.reference_summary,
            source.vendor.replace("_", " "),
            " ".join(source.keywords),
        ]
    ).lower()
    source_tokens = _tokenize(haystack)
    if not source_tokens:
        return 0.2
    overlap = len(query_tokens & source_tokens)
    base = overlap / max(len(query_tokens), 1)
    if source.vendor.replace("_", " ") in query.lower():
        base += 0.25
    if source.preferred_source_types:
        vendor_key = source.vendor.lower()
        for pref in source.preferred_source_types:
            pref_key = pref.lower().replace("_", " ")
            if pref_key in vendor_key or vendor_key in pref_key.replace(" ", "_"):
                base += 0.15
                break
    return min(0.95, 0.25 + base * 0.5)


def select_pack_sources(
    pack_ids: list[str],
    query: str,
    *,
    limit: int = _MAX_PACK_ROWS,
) -> list[tuple[PackSourceDefinition, float]]:
    """Rank catalog sources for assigned packs by query relevance."""
    ensure_pack_sources_registered()
    ranked: list[tuple[PackSourceDefinition, float]] = []
    seen: set[str] = set()
    for pack_id in pack_ids:
        for source in list_sources_for_pack(pack_id):
            if source.id in seen:
                continue
            seen.add(source.id)
            ranked.append((source, score_source_relevance(source, query)))
    ranked.sort(key=lambda row: row[1], reverse=True)
    return ranked[:limit]


def _vendors_for_packs(pack_ids: list[str]) -> tuple[str, ...]:
    vendors: list[str] = []
    seen: set[str] = set()
    for pack_id in pack_ids:
        for vendor in PACK_VENDOR_MAP.get(pack_id, ()):
            v = str(vendor).strip().lower()
            if v and v not in seen:
                seen.add(v)
                vendors.append(v)
    return tuple(vendors)


def _fetch_signals(
    client: Any,
    *,
    org_id: str,
    vendors: tuple[str, ...],
    query: str,
) -> list[dict[str, Any]]:
    if not vendors:
        return []
    try:
        q = (
            client.table("external_signals")
            .select("id, vendor, title, summary, signal_type, payload, detected_at, observed_at")
            .eq("org_id", org_id)
            .order("detected_at", desc=True)
            .limit(_MAX_SIGNALS_PER_VENDOR * max(len(vendors), 1))
        )
        if len(vendors) == 1:
            q = q.eq("vendor", vendors[0])
        else:
            q = q.in_("vendor", list(vendors))
        result = q.execute()
        rows = [row for row in (result.data or []) if isinstance(row, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_source_signals_skipped org_id=%s err=%s", org_id, exc)
        return []

    query_tokens = _tokenize(query)

    def _score(row: dict[str, Any]) -> float:
        text = " ".join(
            str(row.get(key) or "")
            for key in ("title", "summary", "signal_type", "vendor")
        ).lower()
        tokens = _tokenize(text)
        if not query_tokens or not tokens:
            return 0.4
        return 0.3 + len(query_tokens & tokens) / max(len(query_tokens), 1) * 0.6

    rows.sort(key=_score, reverse=True)
    return rows[: _MAX_SIGNALS_PER_VENDOR * max(len(vendors), 1)]


def _fetch_entities(
    client: Any,
    *,
    org_id: str,
    vendors: tuple[str, ...],
    query: str,
) -> list[dict[str, Any]]:
    if not vendors:
        return []
    try:
        q = (
            client.table("external_entities")
            .select("id, vendor, title, entity_type, payload, updated_at")
            .eq("org_id", org_id)
            .order("updated_at", desc=True)
            .limit(_MAX_ENTITIES_PER_VENDOR * max(len(vendors), 1))
        )
        if len(vendors) == 1:
            q = q.eq("vendor", vendors[0])
        else:
            q = q.in_("vendor", list(vendors))
        result = q.execute()
        rows = [row for row in (result.data or []) if isinstance(row, dict)]
    except Exception as exc:  # noqa: BLE001
        logger.debug("pack_source_entities_skipped org_id=%s err=%s", org_id, exc)
        return []

    query_tokens = _tokenize(query)

    def _score(row: dict[str, Any]) -> float:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        text = " ".join(
            [
                str(row.get("title") or ""),
                str(row.get("entity_type") or ""),
                str(row.get("vendor") or ""),
                json.dumps(payload, default=str)[:400],
            ]
        ).lower()
        tokens = _tokenize(text)
        if not query_tokens or not tokens:
            return 0.35
        return 0.25 + len(query_tokens & tokens) / max(len(query_tokens), 1) * 0.65

    rows.sort(key=_score, reverse=True)
    return rows[: _MAX_ENTITIES_PER_VENDOR * max(len(vendors), 1)]


def _signal_content(row: dict[str, Any]) -> str:
    parts = [
        str(row.get("title") or "").strip(),
        str(row.get("summary") or "").strip(),
    ]
    payload = row.get("payload")
    if isinstance(payload, dict) and payload:
        parts.append(json.dumps(payload, default=str)[:600])
    return " — ".join(part for part in parts if part)[:1200]


def _entity_content(row: dict[str, Any]) -> str:
    title = str(row.get("title") or row.get("entity_type") or "Entity").strip()
    payload = row.get("payload")
    if isinstance(payload, dict) and payload:
        return f"{title}: {json.dumps(payload, default=str)[:900]}"
    return title[:1200]


def normalize_catalog_source_row(
    source: PackSourceDefinition,
    *,
    score: float,
    index: int,
) -> dict[str, Any]:
    content = source.reference_summary or f"Intelligence pack source: {source.title} ({source.vendor})"
    return {
        "id": f"pack-catalog-{index}",
        "content": content[:1200],
        "score": round(float(score), 4),
        "source": source.title,
        "title": source.title,
        "kind": "intelligence_pack",
        "metadata": {
            "pack_id": source.pack_id,
            "vendor": source.vendor,
            "source_definition_id": source.id,
            "origin": "catalog",
        },
    }


def normalize_signal_row(row: dict[str, Any], *, pack_id: str, index: int) -> dict[str, Any]:
    vendor = str(row.get("vendor") or "")
    title = str(row.get("title") or row.get("signal_type") or "Pack signal")
    return {
        "id": f"pack-signal-{row.get('id') or index}",
        "content": _signal_content(row),
        "score": 0.72,
        "source": title,
        "title": title,
        "kind": "intelligence_pack",
        "metadata": {
            "pack_id": pack_id,
            "vendor": vendor,
            "signal_type": row.get("signal_type"),
            "origin": "external_signals",
        },
    }


def normalize_entity_row(row: dict[str, Any], *, pack_id: str, index: int) -> dict[str, Any]:
    vendor = str(row.get("vendor") or "")
    title = str(row.get("title") or row.get("entity_type") or "Pack entity")
    return {
        "id": f"pack-entity-{row.get('id') or index}",
        "content": _entity_content(row),
        "score": 0.68,
        "source": title,
        "title": title,
        "kind": "intelligence_pack",
        "metadata": {
            "pack_id": pack_id,
            "vendor": vendor,
            "entity_type": row.get("entity_type"),
            "origin": "external_entities",
        },
    }


def _primary_pack_id(pack_ids: list[str], vendor: str) -> str:
    v = str(vendor or "").strip().lower()
    for pack_id in pack_ids:
        if v in {str(x).lower() for x in PACK_VENDOR_MAP.get(pack_id, ())}:
            return pack_id
    return pack_ids[0] if pack_ids else ""


async def retrieve_pack_sources(
    *,
    client: Any,
    org_id: str,
    query: str,
    knowledge_assignments: list[dict[str, Any]] | None,
    limit: int = _MAX_PACK_ROWS,
) -> dict[str, Any]:
    """Fetch and normalize pack-aware sources for cascade injection."""
    pack_ids = extract_pack_ids(knowledge_assignments)
    if not pack_ids:
        return {"rows": [], "pack_ids": [], "skipped_reason": "no_pack_assignments"}

    selected = select_pack_sources(pack_ids, query, limit=limit)
    vendors = _vendors_for_packs(pack_ids)
    signals = _fetch_signals(client, org_id=org_id, vendors=vendors, query=query)
    entities = _fetch_entities(client, org_id=org_id, vendors=vendors, query=query)

    rows: list[dict[str, Any]] = []
    for index, (source, score) in enumerate(selected):
        rows.append(normalize_catalog_source_row(source, score=score, index=index))

    for index, signal in enumerate(signals):
        pack_id = _primary_pack_id(pack_ids, str(signal.get("vendor") or ""))
        rows.append(normalize_signal_row(signal, pack_id=pack_id, index=index))

    for index, entity in enumerate(entities):
        pack_id = _primary_pack_id(pack_ids, str(entity.get("vendor") or ""))
        rows.append(normalize_entity_row(entity, pack_id=pack_id, index=index))

    rows.sort(key=lambda row: float(row.get("score") or 0.0), reverse=True)
    rows = rows[:limit]

    return {
        "rows": rows,
        "pack_ids": pack_ids,
        "catalog_matches": len(selected),
        "signal_count": len(signals),
        "entity_count": len(entities),
        "vendors": list(vendors),
    }


def format_intelligence_pack_sources_section(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    body = json.dumps(
        [
            {
                "title": row.get("title"),
                "source": row.get("source"),
                "content": row.get("content", "")[:800],
                "pack_id": (row.get("metadata") or {}).get("pack_id"),
                "vendor": (row.get("metadata") or {}).get("vendor"),
                "origin": (row.get("metadata") or {}).get("origin"),
            }
            for row in rows
        ],
        default=str,
    )[:8000]
    return f"<intelligence_pack_sources>\n{body}\n</intelligence_pack_sources>\n"


def attach_intelligence_packs_to_cascade(
    cascade: dict[str, Any],
    *,
    payload: dict[str, Any] | None,
    ran: bool,
    skipped_reason: str | None = None,
) -> dict[str, Any]:
    updated = dict(cascade)
    data = payload or {}
    updated["intelligence_packs"] = {
        "ran": ran,
        "skipped_reason": skipped_reason,
        "result_count": len(data.get("rows") or []),
        "pack_ids": data.get("pack_ids") or [],
        "catalog_matches": int(data.get("catalog_matches") or 0),
        "signal_count": int(data.get("signal_count") or 0),
        "entity_count": int(data.get("entity_count") or 0),
        "vendors": data.get("vendors") or [],
    }
    return updated
