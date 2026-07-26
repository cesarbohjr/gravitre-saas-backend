"""Sensitive-field mention resolver (STA-316 opaque Memory + STA-320 role heuristic).

Resolve order for sensitive WorkflowFieldSpec mentions:
1. Exact/normalized durable alias (`org_entity_resolution_records`) — no Memory opt-in
2. STA-320 Option B role/title cue heuristic (`entity_type=role`) — no Memory opt-in
3. STA-316 opaque-token Memory search — only when memoryEntityEmbeddings opted in

Naming note: STA-316 “Option B” meant opaque-token embeddings. STA-320 “Option B”
means the non-PII role/title heuristic. They are unrelated product choices.

Capability note: opaque-alias vectors still match via exact HMAC tokens. Person-name
fuzzy disambiguation (e.g. ``Sarah`` → ``Sarah Smith``) uses rule-based
``org_entity_resolution_records`` lookup — including first-name aliases promoted
from confirmed tool output — before optional Memory embeddings.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.connectors.action_catalog.models import WorkflowFieldSpec
from app.core.logging import get_logger
from app.services.entity_resolution_store import (
    lookup_fuzzy_resolutions,
    lookup_resolutions,
    normalize_alias,
)
from app.services.memory_entity_embeddings_service import search_memory_by_mention
from app.services.memory_entity_embeddings_settings import (
    load_memory_entity_embeddings_settings,
    memory_embeddings_enabled_for,
)
from app.services.memory_role_title_heuristic import (
    extract_role_title_cues,
    match_by_role_cues,
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
    """Resolve a sensitive-field mention: exact → role heuristic → optional Memory."""
    if not field.sensitive:
        return MemoryResolveResult(status="skipped", reason="field_not_sensitive")

    if getattr(settings, "disable_ai", False):
        return MemoryResolveResult(status="skipped", reason="disable_ai")

    hint = (mention or "").strip()
    if not hint:
        return MemoryResolveResult(status="miss", reason="empty_mention")

    # 1) Exact/normalized durable alias (no embedding, no Memory opt-in).
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

    # 1b) Rule-based fuzzy alias (first-name token, prefix) — no Memory opt-in.
    fuzzy = lookup_fuzzy_resolutions(
        client,
        org_id,
        hint,
        integration=integration,
        entity_type=entity_type if entity_type != "entity" else None,
        limit=10,
    )
    fuzzy = [h for h in fuzzy if h.entity_type == entity_type or entity_type == "entity"]
    if len(fuzzy) == 1:
        return MemoryResolveResult(
            status="bound",
            entity_id=fuzzy[0].entity_id,
            reason="entity_resolution_fuzzy",
        )
    if len(fuzzy) > 1:
        return MemoryResolveResult(
            status="ambiguous",
            candidates=tuple((h.entity_id, h.alias_normalized) for h in fuzzy[:5]),
            reason="entity_resolution_fuzzy_ambiguous",
        )

    # 2) STA-320 Option B — role/title cues (no embedding, no Memory opt-in).
    cues = extract_role_title_cues(hint)
    if cues:
        role = match_by_role_cues(
            client,
            org_id=org_id,
            integration=integration,
            cues=cues,
        )
        if role.status == "bound":
            return MemoryResolveResult(
                status="bound",
                entity_id=role.entity_id,
                candidates=role.candidates,
                reason=role.reason,
            )
        if role.status == "ambiguous":
            return MemoryResolveResult(
                status="ambiguous",
                candidates=role.candidates,
                reason=role.reason,
            )

    # 3) Opaque-token Memory search — STA-316 opt-in only.
    policy = load_memory_entity_embeddings_settings(client, org_id)
    if not memory_embeddings_enabled_for(policy, integration=integration):
        return MemoryResolveResult(status="miss", reason="memory_opt_in_off")

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
