"""Data collectors for the company intelligence learning loop."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client


async def collect_query_corpus(
    settings: Settings,
    org_id: str,
    *,
    since_days: int = 90,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    db = client or get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    result = (
        db.table("user_query_patterns")
        .select(
            "query_text, normalized_query_text, query_category, created_at, user_id, "
            "surface, agent_id, department, is_failed_search, feedback_helpful, rag_quality_score"
        )
        .eq("org_id", org_id)
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(2000)
        .execute()
    )
    return list(result.data or [])


def aggregate_query_categories(queries: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in queries:
        category = str(row.get("query_category") or "general")
        counts[category] += 1
    return dict(counts)


async def collect_org_memory_digest(
    settings: Settings,
    org_id: str,
    *,
    limit: int = 20,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    db = client or get_supabase_client(settings)
    result = (
        db.table("agent_memories")
        .select("id, agent_id, content, category, usage_count, confidence")
        .eq("org_id", org_id)
        .in_("category", ["pattern", "rule", "fact"])
        .order("usage_count", desc=True)
        .limit(limit)
        .execute()
    )
    return list(result.data or [])


def get_active_org_ids(
    settings: Settings,
    *,
    since_days: int = 7,
    limit: int = 20,
    client: Any | None = None,
) -> list[str]:
    db = client or get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    org_ids: set[str] = set()

    for table, org_column in (
        ("user_query_patterns", "org_id"),
        ("workflow_runs", "org_id"),
        ("agent_memories", "org_id"),
    ):
        try:
            rows = (
                db.table(table)
                .select(org_column)
                .gte("created_at", since)
                .limit(500)
                .execute()
                .data
                or []
            )
            for row in rows:
                value = str(row.get(org_column) or "").strip()
                if value:
                    org_ids.add(value)
        except Exception:  # noqa: BLE001
            continue

    ranked = sorted(org_ids)
    return ranked[:limit]


async def fetch_active_workflow_definitions(
    settings: Settings,
    org_id: str,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Workflows with a recent run or explicit active status."""
    db = client or get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
    recent_runs = (
        db.table("workflow_runs")
        .select("workflow_id, definition_snapshot")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .not_.is_("workflow_id", "null")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
        .data
        or []
    )
    by_workflow: dict[str, dict[str, Any]] = {}
    for run in recent_runs:
        wf_id = str(run.get("workflow_id") or "")
        if wf_id and wf_id not in by_workflow:
            by_workflow[wf_id] = {
                "workflow_id": wf_id,
                "definition_snapshot": run.get("definition_snapshot"),
            }
    return list(by_workflow.values())
