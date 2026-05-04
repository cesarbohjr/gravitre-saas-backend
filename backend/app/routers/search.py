"""Semantic search + search history endpoints."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/api/search", tags=["search"])
logger = get_logger(__name__)


class SearchFilters(BaseModel):
    types: list[str] | None = None
    dateRange: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    filters: SearchFilters | None = None


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return (
        "does not exist" in message
        or "relation" in message and "does not exist" in message
        or "undefined_table" in message
    )


def _compute_score(query: str, title: str, description: str) -> float:
    q = query.strip().lower()
    t = title.strip().lower()
    d = description.strip().lower()
    if not q:
        return 0.0
    if t == q:
        return 1.0
    if t.startswith(q):
        return 0.92
    if q in t:
        return 0.85
    if q in d:
        return 0.72
    return 0.6


def _entity_type_allowed(entity_type: str, requested_types: set[str] | None) -> bool:
    if not requested_types:
        return True
    return entity_type in requested_types


@router.post("")
async def search_route(
    body: SearchRequest,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")

    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Search query is required")

    requested_types = (
        {value.strip().lower() for value in body.filters.types if value and value.strip()}
        if body.filters and body.filters.types
        else None
    )
    pattern = f"%{query}%"
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    results: list[dict[str, Any]] = []

    def add_result(
        *,
        item_id: str,
        entity_type: str,
        title: str,
        url: str,
        description: str = "",
        highlight: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not _entity_type_allowed(entity_type, requested_types):
            return
        if not item_id or not title:
            return
        results.append(
            {
                "id": item_id,
                "entity_type": entity_type,
                "title": title,
                "description": description or None,
                "highlight": highlight or None,
                "score": _compute_score(query, title, f"{description} {highlight}"),
                "url": url,
                "metadata": metadata or {},
            }
        )

    try:
        workflows_resp = (
            client.table("workflow_defs")
            .select("id, name, description, status")
            .eq("org_id", org_id)
            .or_(f"name.ilike.{pattern},description.ilike.{pattern}")
            .limit(12)
            .execute()
        )
        if workflows_resp.error and not _is_missing_table_error(workflows_resp.error):
            raise HTTPException(status_code=500, detail=str(workflows_resp.error))
        for workflow in workflows_resp.data or []:
            add_result(
                item_id=str(workflow.get("id") or ""),
                entity_type="workflow",
                title=str(workflow.get("name") or "Workflow"),
                description=str(workflow.get("description") or ""),
                url=f"/workflows/{workflow.get('id')}",
                metadata={"status": workflow.get("status")},
            )

        agents_resp = (
            client.table("operators")
            .select("id, name, description, role, status")
            .eq("org_id", org_id)
            .or_(f"name.ilike.{pattern},description.ilike.{pattern},role.ilike.{pattern}")
            .limit(12)
            .execute()
        )
        if agents_resp.error and not _is_missing_table_error(agents_resp.error):
            raise HTTPException(status_code=500, detail=str(agents_resp.error))
        for agent in agents_resp.data or []:
            add_result(
                item_id=str(agent.get("id") or ""),
                entity_type="agent",
                title=str(agent.get("name") or "Agent"),
                description=str(agent.get("description") or ""),
                highlight=str(agent.get("role") or ""),
                url=f"/agents/{agent.get('id')}",
                metadata={"status": agent.get("status")},
            )

        connectors_resp = (
            client.table("connectors")
            .select("id, name, description, vendor, status")
            .eq("org_id", org_id)
            .or_(f"name.ilike.{pattern},description.ilike.{pattern},vendor.ilike.{pattern}")
            .limit(12)
            .execute()
        )
        if connectors_resp.error and not _is_missing_table_error(connectors_resp.error):
            raise HTTPException(status_code=500, detail=str(connectors_resp.error))
        for connector in connectors_resp.data or []:
            add_result(
                item_id=str(connector.get("id") or ""),
                entity_type="connector",
                title=str(connector.get("name") or "Connector"),
                description=str(connector.get("description") or ""),
                highlight=str(connector.get("vendor") or ""),
                url=f"/connectors/{connector.get('id')}",
                metadata={"status": connector.get("status")},
            )

        sources_resp = (
            client.table("rag_sources")
            .select("id, title, type, metadata")
            .eq("org_id", org_id)
            .or_(f"title.ilike.{pattern},type.ilike.{pattern}")
            .limit(12)
            .execute()
        )
        if sources_resp.error and not _is_missing_table_error(sources_resp.error):
            raise HTTPException(status_code=500, detail=str(sources_resp.error))
        for source in sources_resp.data or []:
            add_result(
                item_id=str(source.get("id") or ""),
                entity_type="source",
                title=str(source.get("title") or "Source"),
                highlight=str(source.get("type") or ""),
                description="RAG source",
                url=f"/sources/{source.get('id')}",
                metadata={"type": source.get("type")},
            )

        runs_resp = (
            client.table("workflow_runs")
            .select("id, status, workflow_id, error")
            .eq("org_id", org_id)
            .or_(f"id.ilike.{pattern},status.ilike.{pattern},error.ilike.{pattern}")
            .limit(12)
            .execute()
        )
        if runs_resp.error and not _is_missing_table_error(runs_resp.error):
            raise HTTPException(status_code=500, detail=str(runs_resp.error))
        for run in runs_resp.data or []:
            add_result(
                item_id=str(run.get("id") or ""),
                entity_type="run",
                title=f"Run {run.get('id')}",
                description=f"Status: {run.get('status') or 'unknown'}",
                highlight=str(run.get("error") or ""),
                url=f"/runs/{run.get('id')}",
                metadata={"workflow_id": run.get("workflow_id")},
            )

        docs_resp = (
            client.table("rag_documents")
            .select("id, title, metadata, source_id")
            .eq("org_id", org_id)
            .ilike("title", pattern)
            .limit(12)
            .execute()
        )
        if docs_resp.error and not _is_missing_table_error(docs_resp.error):
            raise HTTPException(status_code=500, detail=str(docs_resp.error))
        for doc in docs_resp.data or []:
            add_result(
                item_id=str(doc.get("id") or ""),
                entity_type="document",
                title=str(doc.get("title") or "Document"),
                description="Indexed document",
                url=f"/lite/deliverables?documentId={doc.get('id')}",
                metadata={"source_id": doc.get("source_id")},
            )

        results.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        limited_results = results[:50]
        suggestions = [item["title"] for item in limited_results[:5] if item.get("title")]

        history_insert = (
            client.table("search_history")
            .insert(
                {
                    "org_id": org_id,
                    "user_id": user["user_id"],
                    "query": query,
                    "results_count": len(limited_results),
                }
            )
            .execute()
        )
        if history_insert.error and not _is_missing_table_error(history_insert.error):
            raise HTTPException(status_code=500, detail=str(history_insert.error))
    except Exception as exc:  # noqa: BLE001
        logger.warning("search fallback org_id=%s error=%s", org_id, str(exc))
        return {
            "results": [],
            "suggestions": [],
            "totalCount": 0,
            "fallback": True,
        }

    return {
        "results": limited_results,
        "suggestions": suggestions,
        "totalCount": len(limited_results),
    }


@router.get("/history")
async def search_history_route(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("search_history")
        .select("id, query, results_count, created_at")
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .order("created_at", desc=True)
        .limit(30)
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"searches": []}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"searches": list(response.data or [])}


@router.delete("/history/{history_id}")
async def delete_search_history_item_route(
    history_id: str,
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("search_history")
        .delete()
        .eq("id", history_id)
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}


@router.delete("/history")
async def clear_search_history_route(
    user: Annotated[dict, Depends(get_current_user)],
    org_id: Annotated[str | None, Depends(get_org_context)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    if org_id is None:
        raise HTTPException(status_code=403, detail="Organization context required")
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    response = (
        client.table("search_history")
        .delete()
        .eq("org_id", org_id)
        .eq("user_id", user["user_id"])
        .execute()
    )
    if _is_missing_table_error(response.error):
        return {"ok": True}
    if response.error:
        raise HTTPException(status_code=500, detail=str(response.error))
    return {"ok": True}
