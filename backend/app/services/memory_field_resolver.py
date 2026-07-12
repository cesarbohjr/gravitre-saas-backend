"""STA-316 — WorkflowFieldSpec-backed Memory resolver (Option B).

Runs only when:
- org memoryEntityEmbeddings.enabled is true
- field.sensitive is true
- connector allowlisted (if configured)
Falls back to rule-based / clarification; never embeds raw PII.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.connectors.action_catalog.models import WorkflowFieldSpec
from app.core.logging import get_logger
from app.services.entity_resolution_store import lookup_resolutions, normalize_alias
from app.services.memory_entity_embeddings_service import search_memory_by_mention
from app.services.memory_entity_embeddings_settings import (
    load_memory_entity_embeddings_settings,
    memory_embeddings_enabled_for,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class MemoryResolveResult:
    status: str  # bound | ambiguous | miss | skipped
    entity_id: str | None = None
    candidates: tuple[tuple[str, str], ...] = ()  # (entity_id, label)
    reason: str = ""


async def resolve_sensitive_field_mention(
    *,
    client: Any,
    settings: Settings,
    org_id: str,
    integration: str,
    field: WorkflowFieldSpec,
    mention: str,
    entity_type: str = "entity",
    primary_arg_key: str | None = None,
) -> MemoryResolveResult:
    """Resolve a fuzzy mention for a sensitive WorkflowFieldSpec."""
    if not field.sensitive:
        return MemoryResolveResult(status="skipped", reason="field_not_sensitive")

    if getattr(settings, "disable_ai", False):
        return MemoryResolveResult(status="skipped", reason="disable_ai")

    policy = load_memory_entity_embeddings_settings(client, org_id)
    if not memory_embeddings_enabled_for(policy, integration=integration):
        return MemoryResolveResult(status="skipped", reason="org_opt_in_off")

    hint = (mention or "").strip()
    if not hint:
        return MemoryResolveResult(status="miss", reason="empty_mention")

    # 1) Exact/normalized durable alias (no embedding).
    hits = lookup_resolutions(
        client,
        org_id,
        [normalize_alias(hint)],
        integration=integration,
        limit=10,
    )
    exact = [h for h in hits if h.entity_type == entity_type or entity_type == "entity"]
    if len(exact) == 1:
        return MemoryResolveResult(
            status="bound",
            entity_id=exact[0].entity_id,
            reason="entity_resolution_exact",
        )
    if len(exact) > 1:
        return MemoryResolveResult(
            status="ambiguous",
            candidates=tuple((h.entity_id, h.alias_normalized) for h in exact[:5]),
            reason="entity_resolution_ambiguous",
        )

    # 2) Opaque-token Memory search (HMAC(redacted mention) only).
    rows = await search_memory_by_mention(
        client,
        settings,
        org_id=org_id,
        mention=hint,
        integration=integration,
        entity_type=entity_type if entity_type != "entity" else None,
        match_count=5,
        min_score=0.92,
    )
    if not rows:
        return MemoryResolveResult(status="miss", reason="memory_no_match")

    # Collapse to unique entity ids by best score.
    best: dict[str, float] = {}
    for row in rows:
        eid = str(row.get("entity_id") or "").strip()
        if not eid:
            continue
        score = float(row.get("score") or 0.0)
        best[eid] = max(best.get(eid, 0.0), score)

    ranked = sorted(best.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return MemoryResolveResult(status="miss", reason="memory_empty_ids")
    if len(ranked) == 1 or ranked[0][1] >= ranked[1][1] + 0.05:
        return MemoryResolveResult(
            status="bound",
            entity_id=ranked[0][0],
            reason="memory_opaque_match",
        )
    return MemoryResolveResult(
        status="ambiguous",
        candidates=tuple((eid, f"score={score:.3f}") for eid, score in ranked[:5]),
        reason="memory_opaque_ambiguous",
    )


def pick_sensitive_field_for_arg(
    schema_fields: list[WorkflowFieldSpec],
    arg_key: str,
) -> WorkflowFieldSpec | None:
    for field in schema_fields:
        if arg_key in field.arg_keys and field.sensitive:
            return field
    return None
