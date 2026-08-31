"""Knowledge Intelligence v3 — clustering, glossary, and gap identification."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.clustering import QueryClusterer
from app.ml.glossary_extraction import extract_glossary_candidates, map_terms_to_departments
from app.rag.embedding import get_embedding
from app.services.model_router import ModelRouter, TaskType, get_model_router
from app.services.query_normalization import normalize_query
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

GLOSSARY_STATUS_CANDIDATE = "candidate"


async def label_cluster(
    member_queries: list[str],
    *,
    org_id: str,
    router: ModelRouter | None = None,
) -> str:
    """Summarize cluster members into a short label via model_router."""
    samples = member_queries[:8]
    if not samples:
        return "Miscellaneous queries"
    prompt = (
        "Summarize these similar user questions into ONE short topic label (max 8 words). "
        "Return only the label, no punctuation wrapper.\n\n"
        + "\n".join(f"- {q}" for q in samples)
    )
    try:
        active_router = router or get_model_router()
        response = await active_router.complete(
            TaskType.SUMMARIZATION,
            prompt=prompt,
            system_prompt="You label clusters of workplace search queries.",
            org_id=org_id,
            max_tokens=40,
            temperature=0.2,
        )
        label = (response.content or "").strip().strip('"').strip("'")
        return label[:120] if label else "Recurring query theme"
    except Exception as exc:  # noqa: BLE001
        logger.warning("cluster_label_fallback org_id=%s error=%s", org_id, exc)
        return samples[0][:80]


async def suggest_gap_content(
    cluster_label: str,
    member_queries: list[str],
    *,
    org_id: str,
    router: ModelRouter | None = None,
) -> str:
    """Generate actionable documentation suggestion for a knowledge gap."""
    prompt = (
        f"Users repeatedly ask about '{cluster_label}' but searches fail. "
        "Suggest ONE specific document or runbook to add (1-2 sentences).\n\n"
        "Example queries:\n"
        + "\n".join(f"- {q}" for q in member_queries[:6])
    )
    try:
        active_router = router or get_model_router()
        response = await active_router.complete(
            TaskType.CONTENT_GENERATION,
            prompt=prompt,
            system_prompt="You recommend internal documentation gaps for an ops team.",
            org_id=org_id,
            max_tokens=120,
            temperature=0.3,
        )
        return (response.content or "").strip()[:500]
    except Exception as exc:  # noqa: BLE001
        logger.warning("gap_suggestion_fallback org_id=%s error=%s", org_id, exc)
        return f"Consider adding documentation covering {cluster_label}."


def distinct_normalized_count(queries: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    for row in queries:
        text = str(row.get("normalized_query_text") or normalize_query(str(row.get("query_text") or "")))
        if text:
            seen.add(text)
    return len(seen)


MAX_CLUSTER_MATCH_DISTANCE = 1.25


def _representative_query_texts(row: dict[str, Any]) -> list[str]:
    reps = row.get("representative_queries") or []
    if isinstance(reps, str):
        return [reps] if reps else []
    return [str(q) for q in reps if q]


async def resolve_query_cluster_for_bandit(
    settings: Settings,
    org_id: str,
    query_text: str,
    *,
    client: Any | None = None,
    max_clusters: int = 50,
) -> dict[str, Any] | None:
    """Map a live query to the nearest org_query_clusters row for bandit v3 segments."""
    import numpy as np

    normalized = normalize_query(query_text)
    if not normalized:
        return None
    db = client or get_supabase_client(settings)
    try:
        rows = (
            db.table("org_query_clusters")
            .select("id, cluster_label, representative_queries")
            .eq("org_id", org_id)
            .order("computed_at", desc=True)
            .limit(max_clusters)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("query_cluster_resolve_skipped org_id=%s error=%s", org_id, exc)
        return None
    if not rows:
        return None

    for row in rows:
        norm_reps = [normalize_query(text) for text in _representative_query_texts(row)]
        if normalized in norm_reps:
            return {
                "query_cluster_id": str(row["id"]),
                "query_cluster_label": str(row.get("cluster_label") or ""),
                "cluster_match_method": "exact",
            }

    query_emb = np.array(get_embedding(normalized, settings, org_id=org_id), dtype=float)
    rep_rows: list[tuple[str, str, str]] = []
    for row in rows:
        norm_reps = [normalize_query(text) for text in _representative_query_texts(row) if text]
        if not norm_reps:
            continue
        rep_rows.append((str(row["id"]), str(row.get("cluster_label") or ""), norm_reps[0]))

    if not rep_rows:
        return None

    from app.rag.embedding import embed_texts_batch_openai

    rep_texts = [sample for _, _, sample in rep_rows]
    rep_embs = embed_texts_batch_openai(rep_texts, settings, org_id=org_id)
    best_id: str | None = None
    best_label = ""
    best_dist = float("inf")
    for (row_id, label, _), rep_emb in zip(rep_rows, rep_embs, strict=True):
        dist = float(np.linalg.norm(query_emb - np.array(rep_emb, dtype=float)))
        if dist < best_dist:
            best_dist = dist
            best_id = row_id
            best_label = label

    if best_id is None or best_dist > MAX_CLUSTER_MATCH_DISTANCE:
        return None
    return {
        "query_cluster_id": best_id,
        "query_cluster_label": best_label,
        "cluster_match_method": "embedding",
        "cluster_match_distance": round(best_dist, 4),
    }


async def enrich_classification_with_query_cluster(
    classification: dict[str, Any],
    org_id: str,
    query_text: str,
    settings: Settings | None = None,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    if classification.get("query_cluster_id"):
        return classification
    active = settings or get_settings()
    match = await resolve_query_cluster_for_bandit(active, org_id, query_text, client=client)
    if not match:
        return classification
    return {**classification, **match}


def _embed_queries(settings: Settings, org_id: str, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    from app.rag.embedding import embed_texts_batch_openai

    return embed_texts_batch_openai(texts, settings, org_id=org_id)


async def run_query_clustering(
    settings: Settings,
    org_id: str,
    queries: list[dict[str, Any]],
    *,
    client: Any | None = None,
    router: ModelRouter | None = None,
) -> list[dict[str, Any]]:
    """Cluster normalized queries; persist org_query_clusters rows."""
    db = client or get_supabase_client(settings)
    normalized = [
        str(row.get("normalized_query_text") or normalize_query(str(row.get("query_text") or "")))
        for row in queries
    ]
    pairs = [(text, row) for text, row in zip(normalized, queries) if text]
    if len({text for text, _ in pairs}) < 3:
        return []

    # Dedupe by normalized text for clustering, keep representative rows
    unique: dict[str, dict[str, Any]] = {}
    for text, row in pairs:
        unique.setdefault(text, row)
    texts = list(unique.keys())
    embeddings = _embed_queries(settings, org_id, texts)

    clusterer = QueryClusterer(min_cluster_size=3, min_samples=2)
    await clusterer.train(embeddings=embeddings, normalized_queries=texts)

    members = clusterer.cluster_members()
    if not members:
        return []

    # Map failed searches per normalized text
    failed_by_text: dict[str, int] = defaultdict(int)
    total_by_text: dict[str, int] = defaultdict(int)
    for text, row in pairs:
        total_by_text[text] += 1
        if row.get("is_failed_search"):
            failed_by_text[text] += 1

    db.table("org_query_clusters").delete().eq("org_id", org_id).execute()
    results: list[dict[str, Any]] = []
    for cluster_id, member_texts in members.items():
        label = await label_cluster(member_texts, org_id=org_id, router=router)
        failed_count = sum(failed_by_text.get(t, 0) for t in member_texts)
        member_count = sum(total_by_text.get(t, 1) for t in member_texts)
        row_payload = {
            "org_id": org_id,
            "cluster_label": label,
            "member_query_count": member_count,
            "failed_search_count": failed_count,
            "representative_queries": member_texts[:10],
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        inserted = db.table("org_query_clusters").insert(row_payload).execute()
        cluster_row = inserted.data[0] if inserted.data else row_payload
        cluster_row["cluster_id"] = cluster_id
        results.append(cluster_row)
    return results


async def run_glossary_extraction(
    settings: Settings,
    org_id: str,
    queries: list[dict[str, Any]],
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    db = client or get_supabase_client(settings)
    doc_texts: list[str] = []
    try:
        chunks = (
            db.table("rag_chunks")
            .select("content")
            .eq("org_id", org_id)
            .limit(200)
            .execute()
            .data
            or []
        )
        doc_texts = [str(c.get("content") or "") for c in chunks if c.get("content")]
    except Exception:  # noqa: BLE001
        doc_texts = []

    candidates = await extract_glossary_candidates(query_rows=queries, document_texts=doc_texts)
    enriched = map_terms_to_departments(candidates, queries)
    now = datetime.now(timezone.utc).isoformat()
    persisted: list[dict[str, Any]] = []
    for cand in enriched:
        row = {
            "org_id": org_id,
            "term": cand["term"],
            "term_type": cand["term_type"],
            "frequency": cand["frequency"],
            "example_context": cand.get("example_context"),
            "associated_department": cand.get("associated_department"),
            "source": cand["source"],
            "status": GLOSSARY_STATUS_CANDIDATE,
            "last_extracted_at": now,
        }
        db.table("org_glossary_terms").upsert(row, on_conflict="org_id,term").execute()
        persisted.append(row)
    return persisted


async def identify_knowledge_gaps(
    settings: Settings,
    org_id: str,
    cluster_rows: list[dict[str, Any]] | None,
    *,
    client: Any | None = None,
    router: ModelRouter | None = None,
    min_failed: int = 3,
) -> list[dict[str, Any]]:
    """Surface clusters where failed searches dominate."""
    if not cluster_rows:
        return []
    db = client or get_supabase_client(settings)
    db.table("org_knowledge_gaps").delete().eq("org_id", org_id).eq("status", "open").execute()
    gaps: list[dict[str, Any]] = []
    for cluster in cluster_rows:
        failed = int(cluster.get("failed_search_count") or 0)
        if failed < min_failed:
            continue
        label = str(cluster.get("cluster_label") or "Unknown topic")
        reps = cluster.get("representative_queries") or []
        if isinstance(reps, str):
            reps = [reps]
        description = (
            f"{failed} queries about '{label}' failed to find a good answer — "
            "consider adding documentation on this topic."
        )
        suggestion = await suggest_gap_content(label, list(reps), org_id=org_id, router=router)
        payload = {
            "org_id": org_id,
            "cluster_id": cluster.get("id"),
            "description": description,
            "suggested_content": suggestion,
            "failed_query_count": failed,
            "status": "open",
        }
        inserted = db.table("org_knowledge_gaps").insert(payload).execute()
        gaps.append(inserted.data[0] if inserted.data else payload)
    return gaps


async def load_admin_intelligence_snapshot(
    settings: Settings,
    org_id: str,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    db = client or get_supabase_client(settings)
    since = (datetime.now(timezone.utc).replace(microsecond=0)).isoformat()
    queries = (
        db.table("user_query_patterns")
        .select(
            "id, query_text, normalized_query_text, query_category, is_failed_search, "
            "feedback_helpful, surface, department, created_at"
        )
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(500)
        .execute()
        .data
        or []
    )
    clusters = (
        db.table("org_query_clusters")
        .select("*")
        .eq("org_id", org_id)
        .order("computed_at", desc=True)
        .execute()
        .data
        or []
    )
    glossary = (
        db.table("org_glossary_terms")
        .select("*")
        .eq("org_id", org_id)
        .order("frequency", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    gaps = (
        db.table("org_knowledge_gaps")
        .select("*")
        .eq("org_id", org_id)
        .order("identified_at", desc=True)
        .execute()
        .data
        or []
    )
    relationships = (
        db.table("org_entity_relationships")
        .select("*")
        .eq("org_id", org_id)
        .is_("archived_at", "null")
        .order("last_observed_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    failed_recent = [q for q in queries if q.get("is_failed_search")]
    normalized_count = distinct_normalized_count(queries)
    snapshot = {
        "queryVolume": {
            "totalLogged": len(queries),
            "distinctNormalized": normalized_count,
            "failedSearchCount": len(failed_recent),
        },
        "recentFailedSearches": failed_recent[:20],
        "clusters": clusters,
        "glossary": glossary,
        "knowledgeGaps": gaps,
        "entityRelationships": relationships,
    }
    if getattr(settings, "domain_adaptive_learning_enabled", False):
        from app.services.knowledge_freshness_service import get_knowledge_freshness_service
        from app.services.domain_optimization_engine import get_domain_optimization_engine

        snapshot["knowledgeFreshness"] = await get_knowledge_freshness_service(settings).load_admin_summary(
            org_id,
            client=db,
        )
        snapshot["domainOptimization"] = await get_domain_optimization_engine(settings).get_admin_summary(org_id)
    return snapshot
