"""Semantic search + search history endpoints."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import create_client

from app.auth.dependencies import get_current_user, get_org_context
from app.config import Settings, get_settings
from app.core.logging import get_logger

router = APIRouter(prefix="/api/search", tags=["search"])
logger = get_logger(__name__)

SEARCH_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "for",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "today",
        "with",
        "using",
        "active",
        "errors",
        "error",
    }
)

KNOWN_VENDORS = (
    "hubspot",
    "salesforce",
    "slack",
    "zendesk",
    "stripe",
    "quickbooks",
    "google",
    "microsoft",
    "marketo",
)

DEPARTMENT_HINTS = (
    "finance",
    "sales",
    "marketing",
    "operations",
    "support",
    "hr",
    "legal",
)


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


def _search_tokens(query: str) -> list[str]:
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", query.lower())
        if len(token) > 2 and token not in SEARCH_STOPWORDS
    ]
    return tokens


def _quoted_ilike_pattern(keyword: str) -> str:
    safe = keyword.strip().lower()
    if not safe:
        return ""
    return f'"%{safe.replace(chr(34), "")}%"'


def _or_ilike(columns: list[str], keyword: str) -> str | None:
    pattern = _quoted_ilike_pattern(keyword)
    if not pattern:
        return None
    return ",".join(f"{column}.ilike.{pattern}" for column in columns)


def _infer_run_status(query: str) -> str | None:
    lowered = query.lower()
    for status in ("failed", "completed", "running", "pending", "cancelled", "paused"):
        if status in lowered:
            return status
    return None


def _parse_search_intent(query: str) -> dict[str, Any]:
    lowered = query.lower()
    tokens = _search_tokens(query)
    vendor = next((name for name in KNOWN_VENDORS if name in lowered), None)
    department = next((name for name in DEPARTMENT_HINTS if name in lowered), None)
    entity_focus: str | None = None
    if "workflow" in lowered or vendor:
        entity_focus = "workflow"
    elif "run" in lowered or _infer_run_status(query):
        entity_focus = "run"
    elif "connector" in lowered or ("sync" in lowered and "error" in lowered):
        entity_focus = "connector"
    elif "agent" in lowered or department:
        entity_focus = "agent"
    elif "doc" in lowered or "document" in lowered:
        entity_focus = "document"

    environment = None
    if "production" in lowered:
        environment = "production"
    elif "staging" in lowered:
        environment = "staging"

    return {
        "tokens": tokens,
        "run_status": _infer_run_status(query),
        "environment": environment,
        "vendor": vendor,
        "department": department,
        "entity_focus": entity_focus,
        "connector_issue": "sync" in lowered and "error" in lowered,
        "today_only": "today" in lowered,
    }


def _compute_score(query: str, title: str, description: str, *, tokens: list[str] | None = None) -> float:
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
    keyword_tokens = tokens or _search_tokens(query)
    if keyword_tokens:
        hits = sum(1 for token in keyword_tokens if token in t or token in d)
        if hits:
            return min(0.55 + (hits / len(keyword_tokens)) * 0.35, 0.95)
    return 0.6


def _entity_type_allowed(entity_type: str, requested_types: set[str] | None) -> bool:
    if not requested_types:
        return True
    return entity_type in requested_types


def _record_search_history(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    query: str,
    results_count: int,
) -> None:
    try:
        history_insert = (
            client.table("search_history")
            .insert(
                {
                    "org_id": org_id,
                    "user_id": user_id,
                    "query": query,
                    "results_count": results_count,
                }
            )
            .execute()
        )
        if history_insert.error and not _is_missing_table_error(history_insert.error):
            logger.warning("search history insert failed: %s", history_insert.error)
    except Exception as exc:  # noqa: BLE001
        logger.warning("search history insert failed: %s", exc)


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
    intent = _parse_search_intent(query)
    tokens = list(intent["tokens"])
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    results: list[dict[str, Any]] = []
    seen_ids: set[tuple[str, str]] = set()

    def add_result(
        *,
        item_id: str,
        entity_type: str,
        title: str,
        url: str,
        description: str = "",
        highlight: str = "",
        metadata: dict[str, Any] | None = None,
        score_boost: float = 0.0,
    ) -> None:
        if not _entity_type_allowed(entity_type, requested_types):
            return
        if not item_id or not title:
            return
        dedupe_key = (entity_type, item_id)
        if dedupe_key in seen_ids:
            return
        seen_ids.add(dedupe_key)
        score = _compute_score(query, title, f"{description} {highlight}", tokens=tokens) + score_boost
        results.append(
            {
                "id": item_id,
                "entity_type": entity_type,
                "title": title,
                "description": description or None,
                "highlight": highlight or None,
                "score": min(score, 1.0),
                "url": url,
                "metadata": metadata or {},
            }
        )

    def search_table(
        table: str,
        *,
        select: str,
        columns: list[str],
        limit: int = 12,
        extra_eq: dict[str, Any] | None = None,
        extra_filters: list[tuple[str, str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        try:
            request = client.table(table).select(select).eq("org_id", org_id)
            for key, op, value in extra_filters or []:
                if op == "eq":
                    request = request.eq(key, value)
                elif op == "gte":
                    request = request.gte(key, value)
                elif op == "in":
                    request = request.in_(key, value)
            for key, value in (extra_eq or {}).items():
                request = request.eq(key, value)

            keyword_filters = [_or_ilike(columns, token) for token in tokens[:4]]
            keyword_filters = [item for item in keyword_filters if item]
            if not keyword_filters:
                return []
            request = request.or_(",".join(keyword_filters))
            rows: list[dict[str, Any]] = []
            response = request.limit(limit).execute()
            if response.error and not _is_missing_table_error(response.error):
                logger.warning("search %s query failed: %s", table, response.error)
                return rows
            rows.extend(list(response.data or []))
            return rows
        except Exception as exc:  # noqa: BLE001
            logger.warning("search %s query failed: %s", table, exc)
            return []

    # Intent-first queries for natural-language prompts.
    run_status = intent["run_status"]
    if run_status and _entity_type_allowed("run", requested_types):
        try:
            run_query = (
                client.table("workflow_runs")
                .select("id, status, workflow_id, error, environment, created_at")
                .eq("org_id", org_id)
                .eq("status", run_status)
            )
            if intent["environment"]:
                run_query = run_query.eq("environment", intent["environment"])
            if intent["today_only"]:
                since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
                run_query = run_query.gte("created_at", since.isoformat())
            runs = run_query.order("created_at", desc=True).limit(12).execute()
            if runs.error and not _is_missing_table_error(runs.error):
                logger.warning("search run intent query failed: %s", runs.error)
            for run in runs.data or []:
                add_result(
                    item_id=str(run.get("id") or ""),
                    entity_type="run",
                    title=f"Run {run.get('id')}",
                    description=f"Status: {run.get('status') or 'unknown'}",
                    highlight=str(run.get("error") or run_status),
                    url=f"/runs/{run.get('id')}",
                    metadata={"workflow_id": run.get("workflow_id"), "environment": run.get("environment")},
                    score_boost=0.2,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("search run intent query failed: %s", exc)

    if intent["connector_issue"] and _entity_type_allowed("connector", requested_types):
        try:
            connectors = (
                client.table("connectors")
                .select("id, name, description, vendor, type, status")
                .eq("org_id", org_id)
                .in_("status", ["error", "degraded", "failed", "disconnected"])
                .limit(12)
                .execute()
            )
            if connectors.error and not _is_missing_table_error(connectors.error):
                logger.warning("search connector issue query failed: %s", connectors.error)
            for connector in connectors.data or []:
                add_result(
                    item_id=str(connector.get("id") or ""),
                    entity_type="connector",
                    title=str(connector.get("name") or "Connector"),
                    description=str(connector.get("description") or "Connector sync issue"),
                    highlight=str(connector.get("description") or connector.get("status") or "sync error"),
                    url=f"/connectors/{connector.get('id')}",
                    metadata={"status": connector.get("status"), "vendor": connector.get("vendor")},
                    score_boost=0.15,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("search connector issue query failed: %s", exc)

    vendor = intent["vendor"]
    if vendor and _entity_type_allowed("workflow", requested_types):
        vendor_filter = _or_ilike(["name", "description"], vendor)
        if vendor_filter:
            try:
                workflows = (
                    client.table("workflow_defs")
                    .select("id, name, description, status")
                    .eq("org_id", org_id)
                    .or_(vendor_filter)
                    .limit(12)
                    .execute()
                )
                if workflows.error and not _is_missing_table_error(workflows.error):
                    logger.warning("search workflow vendor query failed: %s", workflows.error)
                for workflow in workflows.data or []:
                    add_result(
                        item_id=str(workflow.get("id") or ""),
                        entity_type="workflow",
                        title=str(workflow.get("name") or "Workflow"),
                        description=str(workflow.get("description") or ""),
                        highlight=vendor,
                        url=f"/workflows/{workflow.get('id')}",
                        metadata={"status": workflow.get("status")},
                        score_boost=0.1,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("search workflow vendor query failed: %s", exc)

        if _entity_type_allowed("connector", requested_types):
            vendor_filter = _or_ilike(["vendor", "type", "name"], vendor)
            if vendor_filter:
                try:
                    connectors = (
                        client.table("connectors")
                        .select("id, name, description, vendor, type, status")
                        .eq("org_id", org_id)
                        .or_(vendor_filter)
                        .limit(12)
                        .execute()
                    )
                    if connectors.error and not _is_missing_table_error(connectors.error):
                        logger.warning("search connector vendor query failed: %s", connectors.error)
                    for connector in connectors.data or []:
                        add_result(
                            item_id=str(connector.get("id") or ""),
                            entity_type="connector",
                            title=str(connector.get("name") or "Connector"),
                            description=str(connector.get("description") or ""),
                            highlight=str(connector.get("vendor") or connector.get("type") or vendor),
                            url=f"/connectors/{connector.get('id')}",
                            metadata={"status": connector.get("status")},
                            score_boost=0.08,
                        )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("search connector vendor query failed: %s", exc)

    department = intent["department"]
    if department and _entity_type_allowed("agent", requested_types):
        dept_filter = _or_ilike(["name", "description", "role"], department)
        if dept_filter:
            try:
                agents = (
                    client.table("operators")
                    .select("id, name, description, role, status")
                    .eq("org_id", org_id)
                    .or_(dept_filter)
                    .limit(12)
                    .execute()
                )
                if agents.error and not _is_missing_table_error(agents.error):
                    logger.warning("search agent department query failed: %s", agents.error)
                for agent in agents.data or []:
                    add_result(
                        item_id=str(agent.get("id") or ""),
                        entity_type="agent",
                        title=str(agent.get("name") or "Agent"),
                        description=str(agent.get("description") or ""),
                        highlight=str(agent.get("role") or department),
                        url=f"/agents/{agent.get('id')}",
                        metadata={"status": agent.get("status")},
                        score_boost=0.1,
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("search agent department query failed: %s", exc)

    if "active" in query.lower() and _entity_type_allowed("agent", requested_types):
        try:
            agents = (
                client.table("operators")
                .select("id, name, description, role, status")
                .eq("org_id", org_id)
                .eq("status", "active")
                .limit(12)
                .execute()
            )
            if agents.error and not _is_missing_table_error(agents.error):
                logger.warning("search active agents query failed: %s", agents.error)
            for agent in agents.data or []:
                add_result(
                    item_id=str(agent.get("id") or ""),
                    entity_type="agent",
                    title=str(agent.get("name") or "Agent"),
                    description=str(agent.get("description") or ""),
                    highlight=str(agent.get("role") or "active"),
                    url=f"/agents/{agent.get('id')}",
                    metadata={"status": agent.get("status")},
                    score_boost=0.05,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("search active agents query failed: %s", exc)

    # Keyword fallback across entity tables.
    for workflow in search_table(
        "workflow_defs",
        select="id, name, description, status",
        columns=["name", "description"],
    ):
        add_result(
            item_id=str(workflow.get("id") or ""),
            entity_type="workflow",
            title=str(workflow.get("name") or "Workflow"),
            description=str(workflow.get("description") or ""),
            url=f"/workflows/{workflow.get('id')}",
            metadata={"status": workflow.get("status")},
        )

    for agent in search_table(
        "operators",
        select="id, name, description, role, status",
        columns=["name", "description", "role"],
    ):
        add_result(
            item_id=str(agent.get("id") or ""),
            entity_type="agent",
            title=str(agent.get("name") or "Agent"),
            description=str(agent.get("description") or ""),
            highlight=str(agent.get("role") or ""),
            url=f"/agents/{agent.get('id')}",
            metadata={"status": agent.get("status")},
        )

    for connector in search_table(
        "connectors",
        select="id, name, description, vendor, status",
        columns=["name", "description", "vendor"],
    ):
        add_result(
            item_id=str(connector.get("id") or ""),
            entity_type="connector",
            title=str(connector.get("name") or "Connector"),
            description=str(connector.get("description") or ""),
            highlight=str(connector.get("vendor") or ""),
            url=f"/connectors/{connector.get('id')}",
            metadata={"status": connector.get("status")},
        )

    for source in search_table(
        "rag_sources",
        select="id, title, type, metadata",
        columns=["title", "type"],
    ):
        add_result(
            item_id=str(source.get("id") or ""),
            entity_type="source",
            title=str(source.get("title") or "Source"),
            highlight=str(source.get("type") or ""),
            description="RAG source",
            url=f"/sources/{source.get('id')}",
            metadata={"type": source.get("type")},
        )

    for run in search_table(
        "workflow_runs",
        select="id, status, workflow_id, error",
        columns=["status", "error"],
    ):
        add_result(
            item_id=str(run.get("id") or ""),
            entity_type="run",
            title=f"Run {run.get('id')}",
            description=f"Status: {run.get('status') or 'unknown'}",
            highlight=str(run.get("error") or ""),
            url=f"/runs/{run.get('id')}",
            metadata={"workflow_id": run.get("workflow_id")},
        )

    for doc in search_table(
        "rag_documents",
        select="id, title, metadata, source_id",
        columns=["title"],
    ):
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

    _record_search_history(
        client,
        org_id=org_id,
        user_id=user["user_id"],
        query=query,
        results_count=len(limited_results),
    )

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
