"""Fuzzy name matching for org_knowledge_nodes (create-time duplicate review)."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_NODE_TYPE_TO_GRAPH_ENTITY: dict[str, str] = {
    "company": "company",
    "employee": "employee",
    "customer": "customer",
    "prospect": "prospect",
    "vendor": "vendor",
    "product": "product",
}


def score_name_match(candidate: str, node_name: str) -> int:
    """Return 0–100 match score between two display names."""
    cand = (candidate or "").strip().lower()
    node = (node_name or "").strip().lower()
    if not cand or not node:
        return 0
    if cand == node:
        return 100
    if node.startswith(cand) or cand.startswith(node):
        return 80
    if cand in node or node in cand:
        return 60
    return 0


def find_knowledge_node_matches(
    rows: list[dict[str, Any]],
    name: str,
    *,
    node_type: str | None = None,
    min_score: int = 60,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank knowledge node rows against a proposed name."""
    label = (name or "").strip()
    if not label:
        return []
    want_type = (node_type or "").strip().lower()
    matches: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        node_name = str(row.get("name") or "").strip()
        if not node_name:
            continue
        row_type = str(row.get("node_type") or "").strip().lower()
        if want_type and row_type and row_type != want_type:
            continue
        score = score_name_match(label, node_name)
        if score < min_score:
            continue
        node_id = str(row.get("id") or "").strip()
        if not node_id:
            continue
        entity_type = _NODE_TYPE_TO_GRAPH_ENTITY.get(row_type, row_type or "company")
        matches.append(
            {
                "id": node_id,
                "name": node_name,
                "nodeType": row_type,
                "entityType": entity_type,
                "matchScore": score,
                "source": "confirmed_knowledge",
            }
        )

    matches.sort(key=lambda m: (-int(m.get("matchScore") or 0), str(m.get("name") or "")))
    return matches[: max(1, min(int(limit), 10))]


def find_knowledge_node_matches_for_org(
    client: Any,
    org_id: str,
    name: str,
    *,
    node_type: str | None = None,
    min_score: int = 60,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not client or not org_id:
        return []
    try:
        rows = (
            client.table("org_knowledge_nodes")
            .select("id,node_type,name,created_at")
            .eq("org_id", org_id)
            .limit(500)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("knowledge_node_match_lookup_failed org_id=%s error=%s", org_id, exc)
        return []
    return find_knowledge_node_matches(
        rows,
        name,
        node_type=node_type,
        min_score=min_score,
        limit=limit,
    )
