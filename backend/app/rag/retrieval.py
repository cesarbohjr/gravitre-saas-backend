"""BE-10: Vector search via Supabase RPC; org-scoped only."""
from __future__ import annotations

from typing import Any

from supabase import create_client

from app.config import Settings


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
    environment_name: str = "default",
    source_id: str | None = None,
    document_id: str | None = None,
    department_id: str | None = None,
    agent_id: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Load org-scoped chunk text for in-memory BM25 ranking."""
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
        return []

    query = (
        client.table("rag_chunks")
        .select("id,content,document_id,source_id")
        .eq("org_id", org_id)
        .eq("environment", environment_name)
        .limit(max(limit, 50))
    )
    if source_id:
        query = query.eq("source_id", source_id)
    if document_id:
        query = query.eq("document_id", document_id)
    if scoped_source_ids is not None:
        query = query.in_("source_id", scoped_source_ids)
    response = query.execute()
    rows = list(response.data or [])
    if not rows:
        return []

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
    ]
