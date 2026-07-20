"""v6 one-hop entity relationship traversal and prompt context."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.entity_relationship_builder import (
    BUSINESS_ENTITY_TYPES,
    ENTITY_DEPARTMENT,
    ENTITY_GLOSSARY,
    ENTITY_QUERY_CLUSTER,
    ENTITY_AGENT,
    ENTITY_WORKFLOW_RUN,
    _load_glossary_terms,
    _text_contains_term,
    rebuild_org_entity_relationships,
)
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

_MAX_PROMPT_RELATED = 5


async def get_related_entities(
    org_id: str,
    entity_type: str,
    entity_id: str,
    *,
    max_results: int = 5,
    settings: Settings | None = None,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """One-hop neighbors only, ordered by confidence then evidence_count."""
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    limit = max(1, min(int(max_results), 25))

    outgoing = (
        db.table("org_entity_relationships")
        .select("*")
        .eq("org_id", org_id)
        .eq("source_entity_type", entity_type)
        .eq("source_entity_id", entity_id)
        .execute()
        .data
        or []
    )
    incoming = (
        db.table("org_entity_relationships")
        .select("*")
        .eq("org_id", org_id)
        .eq("target_entity_type", entity_type)
        .eq("target_entity_id", entity_id)
        .execute()
        .data
        or []
    )

    from app.services.confidence_honesty import (
        CONFIDENCE_SOURCE_EDGE_HEURISTIC,
        label_confidence,
    )

    related: list[dict[str, Any]] = []
    for row in outgoing:
        # Stored edge confidence is always a builder heuristic estimate (Module C).
        raw_out = row.get("confidence")
        labeled = label_confidence(
            float(raw_out) if raw_out is not None else None,
            source=CONFIDENCE_SOURCE_EDGE_HEURISTIC,
            is_estimate=True,
        )
        related.append(
            {
                "direction": "outgoing",
                "relationshipType": row.get("relationship_type"),
                "entityType": row.get("target_entity_type"),
                "entityId": row.get("target_entity_id"),
                **labeled,
                "evidenceCount": int(row.get("evidence_count") or 0),
            }
        )
    for row in incoming:
        raw_in = row.get("confidence")
        labeled = label_confidence(
            float(raw_in) if raw_in is not None else None,
            source=CONFIDENCE_SOURCE_EDGE_HEURISTIC,
            is_estimate=True,
        )
        related.append(
            {
                "direction": "incoming",
                "relationshipType": row.get("relationship_type"),
                "entityType": row.get("source_entity_type"),
                "entityId": row.get("source_entity_id"),
                **labeled,
                "evidenceCount": int(row.get("evidence_count") or 0),
            }
        )

    related.sort(
        key=lambda item: (float(item["confidence"]), int(item["evidenceCount"])),
        reverse=True,
    )
    return related[:limit]


def find_matching_glossary_terms(
    text: str,
    glossary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Match task/query text against v3 glossary vocabulary (no new NER)."""
    matches: list[dict[str, Any]] = []
    for row in glossary_rows:
        term = str(row.get("term") or "")
        if term and _text_contains_term(text, term):
            matches.append(row)
    matches.sort(key=lambda row: int(row.get("frequency") or 0), reverse=True)
    return matches


async def _resolve_entity_label(
    db: Any,
    org_id: str,
    entity_type: str,
    entity_id: str,
    glossary_by_id: dict[str, dict[str, Any]],
) -> str:
    if entity_type == ENTITY_GLOSSARY:
        row = glossary_by_id.get(entity_id)
        return str(row.get("term") or entity_id) if row else entity_id
    if entity_type == ENTITY_DEPARTMENT:
        rows = (
            db.table("departments")
            .select("name")
            .eq("org_id", org_id)
            .eq("id", entity_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return str(rows[0].get("name") or entity_id)
        return entity_id
    if entity_type == ENTITY_AGENT:
        rows = (
            db.table("agents")
            .select("name")
            .eq("org_id", org_id)
            .eq("id", entity_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return str(rows[0].get("name") or entity_id)
        return entity_id
    if entity_type == ENTITY_QUERY_CLUSTER:
        rows = (
            db.table("org_query_clusters")
            .select("cluster_label")
            .eq("org_id", org_id)
            .eq("id", entity_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if rows:
            return str(rows[0].get("cluster_label") or entity_id)
        return entity_id
    if entity_type in BUSINESS_ENTITY_TYPES or entity_type == ENTITY_WORKFLOW_RUN:
        return f"{entity_type.replace('_', ' ')}:{entity_id}"
    return entity_id


async def build_entity_context_section(
    org_id: str,
    task_text: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> str:
    """
    Optional prompt section when task references a known glossary term.
    Returns empty string when no match — silent no-op for unrelated queries.
    """
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    if not (task_text or "").strip():
        return ""

    glossary = _load_glossary_terms(db, org_id)
    matches = find_matching_glossary_terms(task_text, glossary)
    if not matches:
        return ""

    glossary_by_id = {str(row["id"]): row for row in glossary if row.get("id")}
    lines: list[str] = []
    seen_terms: set[str] = set()
    for term_row in matches[:2]:
        term_id = str(term_row["id"])
        if term_id in seen_terms:
            continue
        seen_terms.add(term_id)
        term = str(term_row.get("term") or "")
        related = await get_related_entities(
            org_id,
            ENTITY_GLOSSARY,
            term_id,
            max_results=_MAX_PROMPT_RELATED,
            settings=active_settings,
            client=db,
        )
        if not related:
            dept = term_row.get("associated_department")
            if dept:
                lines.append(f"- '{term}' is associated with the {dept} department (from glossary).")
            continue

        rel_bits: list[str] = []
        for rel in related[:_MAX_PROMPT_RELATED]:
            label = await _resolve_entity_label(
                db,
                org_id,
                str(rel["entityType"]),
                str(rel["entityId"]),
                glossary_by_id,
            )
            rel_bits.append(
                f"{rel['relationshipType']} → {rel['entityType']} '{label}' "
                f"(evidence={rel['evidenceCount']}, confidence={rel['confidence']:.2f})"
            )
        lines.append(f"- '{term}': " + "; ".join(rel_bits))

    if not lines:
        return ""
    return "## Related Entities (one hop)\n" + "\n".join(lines)


async def list_relationships_for_entity(
    org_id: str,
    entity_type: str,
    entity_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Admin helper: one-hop related entities with labels."""
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    glossary = _load_glossary_terms(db, org_id)
    glossary_by_id = {str(row["id"]): row for row in glossary if row.get("id")}
    related = await get_related_entities(
        org_id,
        entity_type,
        entity_id,
        max_results=25,
        settings=active_settings,
        client=db,
    )
    enriched: list[dict[str, Any]] = []
    for rel in related:
        label = await _resolve_entity_label(
            db,
            org_id,
            str(rel["entityType"]),
            str(rel["entityId"]),
            glossary_by_id,
        )
        enriched.append({**rel, "entityLabel": label})
    return {
        "entityType": entity_type,
        "entityId": entity_id,
        "relationships": enriched,
    }


async def load_entity_relationships_snapshot(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    db = client or get_supabase_client(settings or get_settings())
    rows = (
        db.table("org_entity_relationships")
        .select("*")
        .eq("org_id", org_id)
        .order("last_observed_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
    glossary = _load_glossary_terms(db, org_id)
    glossary_by_id = {str(row["id"]): row for row in glossary if row.get("id")}
    departments = {
        str(row.get("associated_department") or ""): row
        for row in glossary
        if row.get("associated_department")
    }
    from app.services.confidence_honesty import (
        CONFIDENCE_SOURCE_EDGE_HEURISTIC,
        label_confidence,
    )

    labeled_rows: list[dict[str, Any]] = []
    for row in rows:
        raw = row.get("confidence")
        labeled = label_confidence(
            float(raw) if raw is not None else None,
            source=CONFIDENCE_SOURCE_EDGE_HEURISTIC,
            is_estimate=True,
        )
        labeled_rows.append({**row, **labeled})
    return {
        "total": len(labeled_rows),
        "relationships": labeled_rows,
        "glossaryTerms": glossary,
        "departments": sorted(departments.keys()),
        "glossaryById": {
            gid: str(row.get("term") or "")
            for gid, row in glossary_by_id.items()
        },
    }
