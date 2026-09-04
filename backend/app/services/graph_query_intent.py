"""Detect relationship-shaped queries and resolve org graph entities by name."""
from __future__ import annotations

import re
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_RELATIONSHIP_QUERY = re.compile(
    r"\b("
    r"how\s+(is|are|does|do)\b.{0,120}\b(related|connected|linked|tied|tie)\b|"
    r"relationship\s+between\b|"
    r"what\s+connects\b|"
    r"how\s+does\b.{0,80}\b(relate|connect|link)\b|"
    r"connection\s+between\b"
    r")",
    re.I | re.DOTALL,
)

# Strip boilerplate so secondary topics (e.g. "Q3 pipeline decline") remain.
_RELATIONSHIP_BOILERPLATE = re.compile(
    r"\b(how\s+(is|are|does|do)|related\s+to|connected\s+to|linked\s+to|"
    r"relationship\s+between|what\s+connects|our|the|a|an)\b",
    re.I,
)

_NODE_TYPE_TO_GRAPH_ENTITY: dict[str, str] = {
    "company": "company",
    "customer": "customer",
    "vendor": "vendor",
    "employee": "employee",
    "prospect": "prospect",
    "product": "product",
    "competitor": "company",
    "project": "project",
    "campaign": "campaign",
    "contract": "contract",
    "kpi": "kpi",
    "system": "system",
    "decision": "decision",
}


def is_relationship_traversal_query(question: str) -> bool:
    """True when the user asks how entities connect, not just what one entity is."""
    text = str(question or "").strip()
    if not text:
        return False
    return bool(_RELATIONSHIP_QUERY.search(text))


def extract_relationship_topic_keywords(question: str) -> list[str]:
    """Topic tokens for ranking multi-hop paths (e.g. pipeline, q3, decline)."""
    text = str(question or "").lower()
    text = _RELATIONSHIP_BOILERPLATE.sub(" ", text)
    text = re.sub(r"[^\w\s-]", " ", text)
    stop = {
        "related",
        "connect",
        "connection",
        "linked",
        "between",
        "relate",
        "decline",
        "increase",
        "change",
        "impact",
        "affect",
    }
    tokens: list[str] = []
    for raw in text.split():
        tok = raw.strip("-_")
        if len(tok) < 2 or tok in stop:
            continue
        tokens.append(tok)
    return tokens[:12]


def _name_candidates(question: str) -> list[str]:
    """Heuristic proper-noun / quoted name extraction for graph seed lookup."""
    text = str(question or "")
    quoted = re.findall(r'"([^"]{2,80})"|\'([^\']{2,80})\'', text)
    names: list[str] = []
    for a, b in quoted:
        candidate = (a or b or "").strip()
        if candidate:
            names.append(candidate)
    # Capitalized token runs (Acme Corp, Q3 is skipped by length/heuristics).
    for match in re.finditer(r"\b([A-Z][a-zA-Z0-9&.-]{1,40}(?:\s+[A-Z][a-zA-Z0-9&.-]{1,40}){0,3})\b", text):
        fragment = match.group(1).strip()
        if fragment.lower() not in {"how", "what", "our", "the"}:
            names.append(fragment)
    deduped: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(name)
    return deduped[:6]


def resolve_entity_from_knowledge_nodes(
    org_id: str,
    question: str,
    *,
    client: Any,
) -> dict[str, str] | None:
    """Best-effort name match against org_knowledge_nodes (no LLM)."""
    if not client or not org_id:
        return None
    candidates = _name_candidates(question)
    if not candidates:
        return None
    try:
        rows = (
            client.table("org_knowledge_nodes")
            .select("id,node_type,name")
            .eq("org_id", org_id)
            .limit(500)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("graph_query_node_lookup_failed org_id=%s error=%s", org_id, exc)
        return None

    best: dict[str, str] | None = None
    best_score = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        node_name = str(row.get("name") or "").strip()
        if not node_name:
            continue
        node_lower = node_name.lower()
        node_type = str(row.get("node_type") or "").strip().lower()
        node_id = str(row.get("id") or "").strip()
        if not node_id:
            continue
        for candidate in candidates:
            cand_lower = candidate.lower()
            score = 0
            if cand_lower == node_lower:
                score = 100
            elif node_lower.startswith(cand_lower) or cand_lower.startswith(node_lower):
                score = 80
            elif cand_lower in node_lower or node_lower in cand_lower:
                score = 60
            if score > best_score:
                entity_type = _NODE_TYPE_TO_GRAPH_ENTITY.get(node_type, node_type or "company")
                best_score = score
                best = {
                    "entity_type": entity_type,
                    "entity_id": node_id,
                    "display_name": node_name,
                    "node_type": node_type,
                    "match_score": str(score),
                }
    return best if best_score >= 60 else None


def rank_paths_for_topic(paths: list[dict[str, Any]], topic_keywords: list[str]) -> list[dict[str, Any]]:
    """Re-rank traversal paths when a secondary topic is present in the question."""
    if not paths or not topic_keywords:
        return paths

    def _score(path: dict[str, Any]) -> tuple[int, float]:
        hay = " ".join(
            [
                str(path.get("entityType") or ""),
                str(path.get("entityId") or ""),
                str(path.get("relationshipType") or ""),
                str(path.get("pathSummary") or ""),
            ]
        ).lower()
        hits = sum(1 for kw in topic_keywords if kw in hay)
        return (hits, float(path.get("confidence") or 0))

    return sorted(paths, key=_score, reverse=True)
