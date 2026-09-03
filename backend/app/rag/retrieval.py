"""BE-10: Vector search via Supabase RPC; org-scoped only."""
from __future__ import annotations

from typing import Any

from supabase import create_client

from app.config import Settings
from app.core.logging import get_logger
from app.knowledge_fabric.retrieval import FTS_OPTIONS, build_fts_query

logger = get_logger(__name__)

# Named states for how much of the corpus the keyword arm actually got to rank.
#
# The point of naming these is that they used to be indistinguishable. A corpus
# of 400 chunks and a corpus of 40,000 both produced "here are your BM25
# results", and only one of them was ranking the whole thing. "Ran over
# everything" and "ran over an arbitrary sample" are different facts and must
# never serialise to the same value -- this program's Class C, now booked
# repeatedly.
REACH_EXACT = "exact"  # whole scope fetched; BM25 saw everything
REACH_FTS = "fts_filtered"  # Postgres pre-selected on keywords, then BM25 ranked
REACH_FTS_NO_MATCH = "fts_no_match"  # filter ran, nothing matched. A real answer.
REACH_TRUNCATED = "truncated"  # hit the cap with no keyword filter: a SAMPLE
REACH_NO_TERMS = "no_terms"  # query had no usable keywords; not applicable
REACH_EMPTY = "empty"  # the scope resolved to no sources at all


def search_chunks(
    settings: Settings,
    org_id: str,
    query_embedding: list[float],
    top_k: int = 10,
    source_id: str | None = None,
    document_id: str | None = None,
    environment_name: str = "default",
    department_id: str | None = None,
    agent_id: str | None = None,
) -> list[dict]:
    """Run vector search for org; return list of chunk dicts with score and titles."""
    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    # Serialize embedding for Postgres vector; RPC expects text
    vec_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    payload: dict = {
        "p_org_id": org_id,
        "p_query_embedding": vec_str,
        "p_top_k": top_k,
        "p_source_id": source_id,
        "p_document_id": document_id,
        "p_environment": environment_name,
        "p_department_id": department_id,
        "p_agent_id": agent_id,
    }
    r = client.rpc("rag_search", payload).execute()
    return list(r.data) if r.data else []


def _resolve_source_ids_for_scope(
    client: Any,
    org_id: str,
    environment_name: str,
    *,
    department_id: str | None,
    agent_id: str | None,
) -> list[str] | None:
    if not department_id and not agent_id:
        return None
    query = (
        client.table("rag_sources")
        .select("id,department_id,agent_id")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
    )
    response = query.execute()
    rows = list(response.data or [])
    if not rows:
        return []
    allowed: list[str] = []
    for row in rows:
        source_id = str(row.get("id") or "")
        if not source_id:
            continue
        dept = row.get("department_id")
        agent = row.get("agent_id")
        if department_id and dept and str(dept) != str(department_id):
            continue
        if agent_id and agent and str(agent) != str(agent_id):
            continue
        allowed.append(source_id)
    return allowed


def fetch_bm25_corpus(
    settings: Settings,
    org_id: str,
    *,
    query_text: str = "",
    environment_name: str = "default",
    source_id: str | None = None,
    document_id: str | None = None,
    department_id: str | None = None,
    agent_id: str | None = None,
    limit: int = 500,
) -> tuple[list[dict[str, Any]], str]:
    """Load org-scoped chunk text for BM25 ranking, plus how much of it we got.

    Returns ``(rows, reach)`` where ``reach`` is one of the ``REACH_*`` states.
    The reach is part of the return value rather than an optional out-param
    because the whole defect being fixed here was that it was unobservable: this
    function used to fetch ``limit`` rows with no query terms and no ORDER BY, so
    BM25 ranked an arbitrary slice of the corpus and said nothing about it.

    With a keyword filter the fetch is bounded by *relevance* instead of by
    arbitrary row order, which removes the corpus-size ceiling entirely.

    One real consequence worth naming: BM25's IDF is computed over whatever
    corpus it is handed, so pre-filtering shifts the absolute scores (every
    surviving document now contains at least one query term). Ordering within
    the candidate set still behaves -- rarer and more numerous term matches
    still win -- and the scores are consumed by RRF, which uses rank rather than
    magnitude. It is a change in scale, not in meaning.
    """
    client = create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
    scoped_source_ids = _resolve_source_ids_for_scope(
        client,
        org_id,
        environment_name,
        department_id=department_id,
        agent_id=agent_id,
    )
    if scoped_source_ids is not None and not scoped_source_ids:
        return [], REACH_EMPTY

    capped = max(limit, 50)

    def _base() -> Any:
        # `.limit()` must precede `.text_search()`. postgrest's text_search
        # returns a QueryRequestBuilder, which has no `.limit()` -- calling them
        # the other way round raises AttributeError, and the Fabric's keyword arm
        # was dead for months on exactly that ordering.
        builder = (
            client.table("rag_chunks")
            .select("id,content,document_id,source_id")
            .eq("org_id", org_id)
            .eq("environment", environment_name)
            .limit(capped)
        )
        if source_id:
            builder = builder.eq("source_id", source_id)
        if document_id:
            builder = builder.eq("document_id", document_id)
        if scoped_source_ids is not None:
            builder = builder.in_("source_id", scoped_source_ids)
        return builder

    fts_query = build_fts_query(query_text or "")
    rows: list[dict[str, Any]] = []
    reach = REACH_NO_TERMS

    if fts_query:
        try:
            response = _base().text_search("content_tsv", fts_query, FTS_OPTIONS).execute()
            rows = list(response.data or [])
            reach = REACH_FTS
        except Exception as exc:  # noqa: BLE001
            # Interpolated into the message, not tucked into `extra=`: the log
            # formatter drops `extra`, which is how the Fabric's identical
            # failure stayed invisible while looking like it was being logged.
            logger.warning(
                "rag_bm25_fts_unavailable org_id=%s falling back to unfiltered slice: %s",
                org_id,
                exc,
            )
            fts_query = ""

    if not fts_query:
        response = _base().execute()
        rows = list(response.data or [])
        # The honest distinction. Under the cap this is the entire scope and BM25
        # is exact; at the cap it is a sample, and callers are entitled to know
        # which one they got.
        reach = REACH_TRUNCATED if len(rows) >= capped else (
            REACH_NO_TERMS if not (query_text or "").strip() else REACH_EXACT
        )
        if reach == REACH_TRUNCATED:
            logger.warning(
                "rag_bm25_corpus_truncated org_id=%s env=%s cap=%s — keyword arm is "
                "ranking an arbitrary sample, not the corpus",
                org_id,
                environment_name,
                capped,
            )

    if not rows:
        # Three different reasons to have nothing, kept apart. A keyword filter
        # that ran and matched nothing is a real, informative answer; folding it
        # into "empty" would say the corpus has no content when it may be large
        # and simply not mention these words.
        if reach == REACH_FTS:
            return [], REACH_FTS_NO_MATCH
        return [], REACH_EMPTY

    doc_ids = sorted({str(row.get("document_id")) for row in rows if row.get("document_id")})
    title_map: dict[str, str] = {}
    if doc_ids:
        doc_resp = (
            client.table("rag_documents")
            .select("id,title")
            .eq("org_id", org_id)
            .in_("id", doc_ids)
            .limit(len(doc_ids))
            .execute()
        )
        title_map = {str(doc["id"]): str(doc.get("title") or "") for doc in (doc_resp.data or [])}

    return [
        {
            "id": str(row.get("id") or ""),
            "content": str(row.get("content") or ""),
            "score": 0.0,
            "title": title_map.get(str(row.get("document_id")), ""),
        }
        for row in rows
        if row.get("content")
    ], reach
