"""Per-agent vector memory CRUD and task-time retrieval (STA-49)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from app.config import Settings
from app.rag.department import resolve_department_id_for_agent
from app.rag.embedding import get_embedding
from app.rag.retrieval import search_chunks

VALID_CATEGORIES = frozenset({"fact", "preference", "pattern", "rule"})


def _normalize_category(value: str | None) -> str:
    category = (value or "fact").strip().lower()
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category; expected one of {sorted(VALID_CATEGORIES)}",
        )
    return category


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    return {
        "id": str(row["id"]),
        "agentId": str(row["agent_id"]),
        "content": row.get("content") or "",
        "category": row.get("category") or "fact",
        "provenance": row.get("provenance"),
        "source": row.get("provenance"),
        "confidence": float(row.get("confidence") or 100),
        "usageCount": int(row.get("usage_count") or 0),
        "editable": bool(row.get("editable", True)),
        "createdAt": created_at,
        "updatedAt": updated_at,
    }


def ensure_agent_in_org(client: Any, org_id: str, agent_id: str) -> dict[str, Any]:
    r = (
        client.table("agents")
        .select("id, org_id, name, department, config")
        .eq("org_id", org_id)
        .eq("id", agent_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return r.data[0]


def list_agent_memories(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    category: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    ensure_agent_in_org(client, org_id, agent_id)
    q = (
        client.table("agent_memories")
        .select("*")
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
        .order("created_at", desc=True)
    )
    if category and category != "all":
        q = q.eq("category", _normalize_category(category))
    if query and query.strip():
        q = q.ilike("content", f"%{query.strip()}%")
    rows = q.execute().data or []
    return [_serialize_row(row) for row in rows]


def get_agent_memory(client: Any, org_id: str, agent_id: str, memory_id: str) -> dict[str, Any]:
    ensure_agent_in_org(client, org_id, agent_id)
    r = (
        client.table("agent_memories")
        .select("*")
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
        .eq("id", memory_id)
        .limit(1)
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return _serialize_row(r.data[0])


def create_agent_memory(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    user_id: str | None,
    content: str,
    category: str | None = None,
    provenance: str | None = None,
    confidence: float = 100,
    editable: bool = True,
) -> dict[str, Any]:
    ensure_agent_in_org(client, org_id, agent_id)
    text = (content or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is required")
    embedding = get_embedding(text, settings, org_id=org_id)
    payload: dict[str, Any] = {
        "org_id": org_id,
        "agent_id": agent_id,
        "content": text,
        "category": _normalize_category(category),
        "provenance": (provenance or "").strip() or None,
        "confidence": max(0, min(100, float(confidence))),
        "editable": bool(editable),
        "embedding": embedding,
        "created_by": user_id,
    }
    r = client.table("agent_memories").insert(payload).execute()
    if not r.data:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create memory")
    return _serialize_row(r.data[0])


def update_agent_memory(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    memory_id: str,
    *,
    content: str | None = None,
    category: str | None = None,
    provenance: str | None = None,
    confidence: float | None = None,
    editable: bool | None = None,
) -> dict[str, Any]:
    existing = get_agent_memory(client, org_id, agent_id, memory_id)
    if not existing.get("editable"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Memory is protected and cannot be edited")
    patch: dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if category is not None:
        patch["category"] = _normalize_category(category)
    if provenance is not None:
        patch["provenance"] = provenance.strip() or None
    if confidence is not None:
        patch["confidence"] = max(0, min(100, float(confidence)))
    if editable is not None:
        patch["editable"] = bool(editable)
    if content is not None:
        text = content.strip()
        if not text:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content cannot be empty")
        patch["content"] = text
        patch["embedding"] = get_embedding(text, settings, org_id=org_id)
    r = (
        client.table("agent_memories")
        .update(patch)
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
        .eq("id", memory_id)
        .execute()
    )
    if not r.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    return _serialize_row(r.data[0])


def delete_agent_memory(client: Any, org_id: str, agent_id: str, memory_id: str) -> None:
    existing = get_agent_memory(client, org_id, agent_id, memory_id)
    if not existing.get("editable"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Memory is protected and cannot be deleted")
    client.table("agent_memories").delete().eq("org_id", org_id).eq("agent_id", agent_id).eq("id", memory_id).execute()


def search_agent_memories(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    query: str,
    top_k: int = 10,
    category: str | None = None,
) -> list[dict[str, Any]]:
    ensure_agent_in_org(client, org_id, agent_id)
    text = (query or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query is required")
    top_k = max(1, min(int(top_k), 50))
    embedding = get_embedding(text, settings, org_id=org_id)
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    payload: dict[str, Any] = {
        "p_org_id": org_id,
        "p_agent_id": agent_id,
        "p_query_embedding": vec_str,
        "p_top_k": top_k,
        "p_category": _normalize_category(category) if category and category != "all" else None,
    }
    r = client.rpc("agent_memory_search", payload).execute()
    rows = list(r.data or [])
    memory_ids = [str(row["memory_id"]) for row in rows if row.get("memory_id")]
    if memory_ids:
        increment_memory_usage(client, memory_ids)
    return [
        {
            "id": str(row["memory_id"]),
            "content": row.get("content") or "",
            "category": row.get("category") or "fact",
            "provenance": row.get("provenance"),
            "source": row.get("provenance"),
            "confidence": float(row.get("confidence") or 100),
            "usageCount": int(row.get("usage_count") or 0) + 1,
            "editable": bool(row.get("editable", True)),
            "score": round(float(row.get("score") or 0), 6),
            "createdAt": row.get("created_at"),
        }
        for row in rows
    ]


def increment_memory_usage(client: Any, memory_ids: list[str]) -> None:
    for memory_id in memory_ids:
        r = client.table("agent_memories").select("usage_count").eq("id", memory_id).limit(1).execute()
        if not r.data:
            continue
        count = int(r.data[0].get("usage_count") or 0) + 1
        client.table("agent_memories").update({"usage_count": count}).eq("id", memory_id).execute()


def _memory_retrieval_enabled(agent: dict[str, Any], parameters: dict[str, Any] | None) -> bool:
    params = parameters or {}
    if "include_agent_memory" in params:
        return bool(params.get("include_agent_memory"))
    config = agent.get("config") or {}
    if isinstance(config, dict):
        return bool(config.get("use_memory") or config.get("include_agent_memory"))
    return False


def _department_rag_enabled(agent: dict[str, Any], parameters: dict[str, Any] | None) -> bool:
    params = parameters or {}
    if "include_department_rag" in params:
        return bool(params.get("include_department_rag"))
    config = agent.get("config") or {}
    if isinstance(config, dict):
        return bool(config.get("include_department_rag"))
    return False


def build_task_retrieval_context(
    settings: Settings,
    client: Any,
    *,
    org_id: str,
    agent: dict[str, Any],
    task: str,
    parameters: dict[str, Any] | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """Retrieve agent memories and optional department RAG for task execution."""
    context: dict[str, Any] = {"memories": [], "rag_chunks": []}
    agent_id = str(agent.get("id") or "")
    if not agent_id:
        return context

    if _memory_retrieval_enabled(agent, parameters):
        try:
            context["memories"] = search_agent_memories(
                settings,
                client,
                org_id,
                agent_id,
                query=task.strip(),
                top_k=top_k,
            )
        except Exception:  # noqa: BLE001
            context["memories"] = []

    if _department_rag_enabled(agent, parameters):
        try:
            department_id, rag_agent_id = resolve_department_id_for_agent(client, org_id, agent_id)
            embedding = get_embedding(task.strip(), settings, org_id=org_id)
            rows = search_chunks(
                settings=settings,
                org_id=org_id,
                query_embedding=embedding,
                top_k=top_k,
                department_id=department_id,
                agent_id=rag_agent_id,
            )
            context["rag_chunks"] = [
                {
                    "content": row.get("content") or "",
                    "score": round(float(row.get("score") or 0), 6),
                    "source_title": row.get("source_title") or "",
                    "document_title": row.get("document_title") or "",
                }
                for row in rows
            ]
        except Exception:  # noqa: BLE001
            context["rag_chunks"] = []

    return context


def format_retrieval_prompt_section(context: dict[str, Any]) -> str:
    """Serialize retrieval context for inclusion in agent prompts."""
    if not context.get("memories") and not context.get("rag_chunks"):
        return ""
    return f"<agent_memory_context>{json.dumps(context, default=str)[:12000]}</agent_memory_context>\n"
