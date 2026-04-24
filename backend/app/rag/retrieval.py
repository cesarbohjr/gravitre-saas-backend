"""BE-10: Vector search via Supabase RPC; org-scoped only."""
from __future__ import annotations

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
    }
    r = client.rpc("rag_search", payload).execute()
    return list(r.data) if r.data else []
