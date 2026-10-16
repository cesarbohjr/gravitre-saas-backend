"""Data collectors for the company intelligence learning loop."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings, get_settings
from app.workflows.repository import get_supabase_client
from app.core.safe_dict import safe_normalize_stored_dict
from app.services.memory_source_liveness import (
    drop_memories_from_revoked_sources, liveness_enabled, observation_columns,
)


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
        .select(observation_columns("id, agent_id, content, category, usage_count, confidence", settings))
        .eq("org_id", org_id)
        .eq("is_active", True)
        .in_("category", ["pattern", "rule", "fact"])
        .order("usage_count", desc=True)
        .limit(limit)
        .execute()
    )
    return drop_memories_from_revoked_sources(
        db, org_id, list(result.data or []), settings=settings, surface="company_intelligence_digest",
    )


def _memory_fingerprint(row: dict[str, Any]) -> str:
    payload = {key: row.get(key) for key in ("id", "content", "category", "source_connector_id")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def memory_digest_provenance(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """References to the exact three memories included by the existing synthesizer."""
    return {"version": 1, "memories": [
        {"id": str(row.get("id") or ""), "fingerprint": _memory_fingerprint(row)}
        for row in rows[:3]
    ]}


def snapshot_memory_digest_is_live(client: Any, org_id: str, snapshot: dict[str, Any],
                                  settings: Settings) -> bool:
    """Revalidate derived memory text before any chat/voice prompt consumes it."""
    if not liveness_enabled(settings):
        return True
    signals = safe_normalize_stored_dict(snapshot.get("signals_json"))
    provenance = safe_normalize_stored_dict(signals.get("memory_digest_provenance"))
    if provenance.get("version") != 1:
        counts = safe_normalize_stored_dict(snapshot.get("source_counts"))
        return counts.get("memory_rows") == 0
    refs = provenance.get("memories")
    if not isinstance(refs, list) or len(refs) > 3:
        return False
    if not refs:
        return True
    if any(not isinstance(ref, dict) or not ref.get("id") or not ref.get("fingerprint") for ref in refs):
        return False
    ids = [str(ref["id"]) for ref in refs]
    try:
        rows = (client.table("agent_memories")
                .select("id,content,category,source_connector_id")
                .eq("org_id", org_id).eq("is_active", True).in_("id", ids)
                .execute().data or [])
        live = drop_memories_from_revoked_sources(
            client, org_id, rows, settings=settings, surface="company_intelligence_snapshot",
        )
        fingerprints = {str(row.get("id")): _memory_fingerprint(row) for row in live}
        return all(fingerprints.get(str(ref["id"])) == ref["fingerprint"] for ref in refs)
    except Exception:  # noqa: BLE001 - source uncertainty must not enter prompts
        return False


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
