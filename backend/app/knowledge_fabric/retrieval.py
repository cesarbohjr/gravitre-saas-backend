"""Hybrid retrieval over platform knowledge_* — vector + FTS + authority/freshness."""
from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.knowledge_fabric.router import KnowledgeRoute, classify_knowledge_query
from app.rag.embedding import get_embedding
from app.services.retrieval_provenance import build_provenance_envelope

logger = get_logger(__name__)


def _authority_boost(authority: float, freshness: float) -> float:
    return 0.55 * float(authority or 0) + 0.25 * float(freshness or 0)


def rerank_with_authority(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure high-authority sources are not outranked by weak semantic-only hits."""
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in candidates:
        semantic = float(row.get("semantic_score") or row.get("score") or 0.0)
        authority = float(row.get("authority_score") or 0.0)
        freshness = float(row.get("freshness_score") or 0.0)
        # Cap semantic so a low-authority web-like hit cannot dominate a regulation.
        capped_semantic = min(semantic, 0.72) if authority < 0.7 else semantic
        final = 0.45 * capped_semantic + _authority_boost(authority, freshness)
        row = dict(row)
        row["score"] = final
        row["semantic_score"] = semantic
        scored.append((final, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored]


def retrieve_knowledge_fabric(
    client: Any,
    query: str,
    *,
    route: KnowledgeRoute | None = None,
    assigned_pack_ids: list[str] | None = None,
    agent_department: str | None = None,
    top_k: int = 6,
    settings: Settings | None = None,
    embed_query: bool = True,
) -> dict[str, Any]:
    settings = settings or get_settings()
    route = route or classify_knowledge_query(
        query,
        assigned_pack_ids=assigned_pack_ids,
        agent_department=agent_department,
    )
    if "expert_pack" not in route.tiers:
        return {"route": route.to_dict(), "results": [], "provenance": []}

    # Resolve source UUIDs for packs / departments
    source_q = client.table("knowledge_sources").select("id,source_id,department,authority_score,metadata,license_type,publisher,url").eq(
        "namespace", "platform_shared"
    ).eq("status", "active")
    sources = source_q.execute().data or []
    allowed_ids: list[str] = []
    pack_filter = set(route.pack_ids or [])
    for s in sources:
        meta = s.get("metadata") if isinstance(s.get("metadata"), dict) else {}
        pack_id = meta.get("pack_id")
        if pack_filter and pack_id not in pack_filter:
            continue
        if route.departments and s.get("department") not in route.departments and not pack_filter:
            continue
        allowed_ids.append(s["id"])
    if not allowed_ids:
        return {"route": route.to_dict(), "results": [], "provenance": []}

    candidates: list[dict[str, Any]] = []

    # FTS path
    try:
        fts = (
            client.table("knowledge_chunks")
            .select("id,content,citation,jurisdiction,authority_score,freshness_score,topics,source_id,document_id,metadata")
            .in_("source_id", allowed_ids)
            .text_search("content_tsv", query, config="english")
            .limit(top_k * 3)
            .execute()
        )
        for row in fts.data or []:
            if route.jurisdictions:
                j = (row.get("jurisdiction") or "").upper()
                if j and not any(j in code.upper() or code.upper() in j for code in route.jurisdictions):
                    # Keep federal when state asked if no state-specific rows
                    if "US-FEDERAL" not in j and "US" != j:
                        continue
            candidates.append(
                {
                    **row,
                    "semantic_score": 0.55,
                    "match": "fts",
                }
            )
    except Exception as exc:  # noqa: BLE001
        logger.info("knowledge_fabric.fts_unavailable", extra={"error": str(exc)[:160]})

    # Vector path
    if embed_query:
        try:
            qvec = get_embedding(query, settings)
            # RPC preferred; fallback: fetch recent chunks and cosine in Python
            rpc = None
            try:
                rpc = client.rpc(
                    "match_knowledge_chunks",
                    {
                        "query_embedding": qvec,
                        "match_count": top_k * 3,
                        "source_ids": allowed_ids,
                    },
                ).execute()
            except Exception:  # noqa: BLE001
                rpc = None
            if rpc and rpc.data:
                for row in rpc.data:
                    candidates.append({**row, "semantic_score": float(row.get("similarity") or 0.5), "match": "vector"})
            else:
                chunk_rows = (
                    client.table("knowledge_chunks")
                    .select("id,content,citation,jurisdiction,authority_score,freshness_score,topics,source_id,document_id,metadata,embedding")
                    .in_("source_id", allowed_ids)
                    .not_.is_("embedding", "null")
                    .limit(80)
                    .execute()
                )
                for row in chunk_rows.data or []:
                    emb = row.get("embedding")
                    if not emb:
                        continue
                    sim = _cosine(qvec, emb)
                    candidates.append({**row, "semantic_score": sim, "match": "vector_local"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("knowledge_fabric.vector_failed", extra={"error": str(exc)[:160]})

    # Dedup by chunk id
    by_id: dict[str, dict[str, Any]] = {}
    for c in candidates:
        cid = str(c.get("id") or "")
        if not cid:
            continue
        prev = by_id.get(cid)
        if not prev or float(c.get("semantic_score") or 0) > float(prev.get("semantic_score") or 0):
            by_id[cid] = c

    ranked = rerank_with_authority(list(by_id.values()))[:top_k]
    source_map = {s["id"]: s for s in sources}
    provenance = []
    results = []
    for row in ranked:
        src = source_map.get(row.get("source_id"), {})
        prov = build_provenance_envelope(
            source_system="knowledge_fabric",
            source_name=str(src.get("publisher") or "Platform knowledge"),
            source_type="knowledge_pack_chunk",
            source_id=str(src.get("source_id") or row.get("source_id") or ""),
            last_updated=None,
            freshness_score=float(row.get("freshness_score") or 0.8),
            confidence=float(row.get("score") or 0),
            reference_only=True,
            extra={
                "authority_score": float(row.get("authority_score") or 0),
                "authority_is_estimate": False,
                "authority_source": "knowledge_source_registry",
                "citation": row.get("citation"),
                "jurisdiction": row.get("jurisdiction"),
                "license_type": src.get("license_type"),
                "web_link": src.get("url"),
                "match": row.get("match"),
            },
        )
        provenance.append(prov)
        results.append(
            {
                "id": row.get("id"),
                "content": row.get("content"),
                "score": row.get("score"),
                "citation": row.get("citation"),
                "jurisdiction": row.get("jurisdiction"),
                "authority_score": row.get("authority_score"),
                "freshness_score": row.get("freshness_score"),
                "source_id": src.get("source_id"),
                "publisher": src.get("publisher"),
            }
        )
    return {"route": route.to_dict(), "results": results, "provenance": provenance}


def _cosine(a: list[float], b: Any) -> float:
    if isinstance(b, str):
        # pgvector may return string form
        b = [float(x) for x in b.strip("[]").split(",") if x.strip()]
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return max(0.0, min(1.0, dot / (na * nb)))
