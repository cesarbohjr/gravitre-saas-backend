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


def detect_agent_memory_conflicts(memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Surface opposing statements across retrieved agent memories."""
    from app.services.context_conflict_detection import _has_opposing_sentiment

    conflicts: list[dict[str, Any]] = []
    for index, left in enumerate(memories):
        left_text = str(left.get("content") or left.get("memory_text") or "")
        if not left_text.strip():
            continue
        for right in memories[index + 1 :]:
            right_text = str(right.get("content") or right.get("memory_text") or "")
            if not right_text.strip():
                continue
            if _has_opposing_sentiment(left_text, right_text):
                conflicts.append(
                    {
                        "memory_a_id": left.get("id"),
                        "memory_b_id": right.get("id"),
                        "category_a": left.get("category"),
                        "category_b": right.get("category"),
                        "requires_human_review": True,
                    }
                )
    return conflicts


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
        client.table("agent_memories").update(
            {"usage_count": count, "last_retrieved_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", memory_id).execute()


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
        context["memory_conflicts"] = detect_agent_memory_conflicts(context["memories"])

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


MIN_DECISIONS_FOR_PATTERN = 3


async def remember_user_preference(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    preference_description: str,
    source: str,
    confidence: float = 0.7,
) -> None:
    create_agent_memory(
        settings,
        client,
        org_id,
        agent_id,
        user_id=None,
        content=f"User preference: {preference_description}",
        category="preference",
        provenance=source,
        confidence=confidence * 100,
    )


async def remember_workflow_outcome(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    workflow_id: str,
    outcome: str,
    key_insight: str,
) -> None:
    create_agent_memory(
        settings,
        client,
        org_id,
        agent_id,
        user_id=None,
        content=f"Workflow {workflow_id} outcome={outcome}: {key_insight}",
        category="pattern",
        provenance="outcome_learning",
        confidence=70,
    )


async def remember_approval_pattern(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    pattern_description: str,
    evidence_count: int,
) -> None:
    if evidence_count < MIN_DECISIONS_FOR_PATTERN:
        return
    create_agent_memory(
        settings,
        client,
        org_id,
        agent_id,
        user_id=None,
        content=f"Approval pattern ({evidence_count} decisions): {pattern_description}",
        category="pattern",
        provenance="outcome_learning",
        confidence=min(95, 50 + evidence_count * 5),
    )


async def remember_prediction_outcome(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    model_name: str,
    prediction_accuracy: float,
    task_type: str,
) -> None:
    create_agent_memory(
        settings,
        client,
        org_id,
        agent_id,
        user_id=None,
        content=f"Model {model_name} accuracy={prediction_accuracy:.2f} on {task_type}",
        category="fact",
        provenance="outcome_learning",
        confidence=prediction_accuracy * 100,
    )


async def get_relevant_agent_memory(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    query: str,
    memory_categories: list[str] | None = None,
) -> list[dict[str, Any]]:
    if memory_categories:
        results: list[dict[str, Any]] = []
        for category in memory_categories:
            results.extend(list_agent_memories(client, org_id, agent_id, category=category, query=query))
        return results
    return search_agent_memories(settings, client, org_id, agent_id, query)


async def update_agent_memory_from_outcome(
    settings: Settings,
    client: Any,
    org_id: str,
    agent_id: str,
    outcome_event: str,
    outcome_data: dict[str, Any],
) -> None:
    import asyncio

    async def _run() -> None:
        if outcome_event in {"workflow_executed", "workflow_failed"}:
            await remember_workflow_outcome(
                settings,
                client,
                org_id,
                agent_id,
                str(outcome_data.get("workflow_id") or ""),
                "success" if outcome_event == "workflow_executed" else "failure",
                str(outcome_data.get("key_insight") or outcome_data.get("task_description") or outcome_event),
            )
        elif outcome_event == "user_feedback_positive":
            await remember_user_preference(
                settings,
                client,
                org_id,
                agent_id,
                str(outcome_data.get("preference_description") or "positive feedback"),
                str(outcome_data.get("source") or "outcome_learning"),
            )
        elif outcome_event == "approval_granted":
            await remember_approval_pattern(
                settings,
                client,
                org_id,
                agent_id,
                str(outcome_data.get("pattern_description") or "approval granted"),
                int(outcome_data.get("evidence_count") or MIN_DECISIONS_FOR_PATTERN),
            )
        elif outcome_event == "prediction_validated":
            await remember_prediction_outcome(
                settings,
                client,
                org_id,
                agent_id,
                str(outcome_data.get("model_name") or "unknown"),
                float(outcome_data.get("prediction_accuracy") or 0.5),
                str(outcome_data.get("task_type") or "unknown"),
            )

    asyncio.create_task(_run())


MEMORY_SCOPE_NOTE = (
    "Organizational memory lineage reads agent_memory_promotion_audit only. "
    "Freshness scoring is advisory for review/expire decisions."
)


class AgentMemoryIntelligenceService:
    """Lineage, freshness, and explainability for agent memories (v4 audit preserved)."""

    def __init__(self, settings: Settings | None = None) -> None:
        from app.config import get_settings

        self.settings = settings or get_settings()

    def _client(self, client: Any | None) -> Any:
        from app.workflows.repository import get_supabase_client

        return client or get_supabase_client(self.settings)

    async def get_memory_lineage(
        self,
        org_id: str,
        memory_id: str,
        *,
        client: Any | None = None,
    ) -> dict[str, Any]:
        db = self._client(client)
        memory_rows = (
            db.table("agent_memories")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", memory_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not memory_rows:
            return {
                "memory_id": memory_id,
                "current_status": "not_found",
                "why_this_was_remembered": "Memory record not found.",
                "scope_note": MEMORY_SCOPE_NOTE,
            }
        memory = memory_rows[0]
        audit_rows = (
            db.table("agent_memory_promotion_audit")
            .select("*")
            .eq("org_id", org_id)
            .eq("memory_id", memory_id)
            .order("created_at", desc=False)
            .execute()
            .data
            or []
        )
        promotion_path = [
            {
                "action": row.get("action"),
                "actor_id": row.get("actor_id"),
                "created_at": row.get("created_at"),
                "notes": row.get("notes"),
            }
            for row in audit_rows
        ]
        human_approved = next((r for r in audit_rows if r.get("action") == "approved"), None)
        auto_promoted = any(r.get("action") == "auto_promoted" for r in audit_rows)
        origin = promotion_path[0] if promotion_path else None
        why = str(memory.get("provenance") or memory.get("content") or "Observed org activity")
        if human_approved:
            why = f"Approved by admin on {human_approved.get('created_at')}. {why}"
        elif auto_promoted:
            why = f"Auto-promoted from repeated org signals. {why}"
        return {
            "memory_id": memory_id,
            "origin_event": origin,
            "promotion_path": promotion_path,
            "human_approved_by": human_approved.get("actor_id") if human_approved else None,
            "auto_promoted": auto_promoted,
            "current_status": "active",
            "why_this_was_remembered": why[:500],
            "scope_note": MEMORY_SCOPE_NOTE,
        }

    async def calculate_memory_freshness(
        self,
        org_id: str,
        memory_id: str,
        *,
        client: Any | None = None,
    ) -> dict[str, Any]:
        db = self._client(client)
        rows = (
            db.table("agent_memories")
            .select("last_retrieved_at, usage_count, updated_at")
            .eq("org_id", org_id)
            .eq("id", memory_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return {
                "freshness_score": 0.0,
                "freshness_label": "stale",
                "recommendation": "expire",
                "scope_note": MEMORY_SCOPE_NOTE,
            }
        row = rows[0]
        last = row.get("last_retrieved_at") or row.get("updated_at")
        days_since = 999
        if last:
            try:
                last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
                days_since = max(0, int((datetime.now(timezone.utc) - last_dt).total_seconds() // 86400))
            except ValueError:
                pass
        usage = int(row.get("usage_count") or 0)
        freshness_score = max(0.0, min(1.0, 1.0 - (days_since / 90.0) * 0.6 + min(usage, 20) * 0.02))
        if freshness_score >= 0.7:
            label = "fresh"
            recommendation = "keep"
        elif freshness_score >= 0.4:
            label = "aging"
            recommendation = "review"
        else:
            label = "stale"
            recommendation = "expire"
        return {
            "freshness_score": round(freshness_score, 4),
            "freshness_label": label,
            "last_retrieved_at": last,
            "days_since_retrieval": days_since,
            "recommendation": recommendation,
            "scope_note": MEMORY_SCOPE_NOTE,
        }

    async def explain_why_gravitre_knows_this(
        self,
        org_id: str,
        memory_id: str,
        *,
        client: Any | None = None,
    ) -> str:
        lineage = await self.get_memory_lineage(org_id, memory_id, client=client)
        freshness = await self.calculate_memory_freshness(org_id, memory_id, client=client)
        return (
            f"{lineage['why_this_was_remembered']} "
            f"Status: {freshness['freshness_label']}."
        )


_memory_intel: AgentMemoryIntelligenceService | None = None


def get_agent_memory_intelligence_service(settings: Settings | None = None) -> AgentMemoryIntelligenceService:
    global _memory_intel
    if _memory_intel is None or settings is not None:
        _memory_intel = AgentMemoryIntelligenceService(settings)
    return _memory_intel

