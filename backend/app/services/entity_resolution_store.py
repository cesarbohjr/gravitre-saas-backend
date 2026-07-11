"""Wave 5 — durable org-level entity resolution (session → longer-term).

Stores alias → entity_id mappings so connector plans can bind across conversations.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.services.query_normalization import normalize_query

logger = get_logger(__name__)

TABLE = "org_entity_resolution_records"

# Map session attribute keys → entity_type for durable storage.
_ATTR_ENTITY_TYPES: dict[str, str] = {
    "email": "contact",
    "contact_id": "contact",
    "company_id": "company",
    "name": "named_entity",
    "list_id": "list",
}


@dataclass(frozen=True)
class ResolutionHit:
    alias_normalized: str
    entity_type: str
    entity_id: str
    integration: str
    source: str
    confidence: float


def normalize_alias(text: str) -> str:
    return normalize_query(text)[:200]


def upsert_resolution(
    client: Any,
    *,
    org_id: str,
    alias: str,
    entity_type: str,
    entity_id: str,
    integration: str,
    source: str = "tool_output",
    confidence: float = 0.7,
    conversation_id: str | None = None,
) -> bool:
    """Insert or bump evidence for an alias → entity mapping. Never raises."""
    from datetime import datetime, timezone

    alias_norm = normalize_alias(alias)
    entity_id_s = str(entity_id or "").strip()
    entity_type_s = str(entity_type or "").strip() or "entity"
    integration_s = str(integration or "").strip().lower()
    if not org_id or not alias_norm or not entity_id_s:
        return False
    conf = max(0.0, min(1.0, float(confidence)))
    now = datetime.now(timezone.utc).isoformat()
    try:
        existing = (
            client.table(TABLE)
            .select("id, evidence_count, confidence")
            .eq("org_id", org_id)
            .eq("integration", integration_s)
            .eq("alias_normalized", alias_norm)
            .eq("entity_type", entity_type_s)
            .limit(1)
            .execute()
        )
        if existing.data:
            prev = existing.data[0]
            evidence = int(prev.get("evidence_count") or 1) + 1
            prev_conf = float(prev.get("confidence") or conf)
            client.table(TABLE).update(
                {
                    "entity_id": entity_id_s,
                    "source": str(source or "tool_output")[:64],
                    "confidence": max(prev_conf, conf),
                    "evidence_count": evidence,
                    "last_observed_at": now,
                    "updated_at": now,
                }
            ).eq("id", prev["id"]).execute()
        else:
            insert_row: dict[str, Any] = {
                "org_id": org_id,
                "alias_normalized": alias_norm,
                "entity_type": entity_type_s,
                "entity_id": entity_id_s,
                "integration": integration_s,
                "source": str(source or "tool_output")[:64],
                "confidence": conf,
                "evidence_count": 1,
                "last_observed_at": now,
                "updated_at": now,
            }
            if conversation_id:
                insert_row["created_by_conversation_id"] = conversation_id
            client.table(TABLE).insert(insert_row).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "entity_resolution_upsert_skipped org_id=%s alias=%s error=%s",
            org_id,
            alias_norm,
            exc,
        )
        return False


def lookup_resolutions(
    client: Any,
    org_id: str,
    aliases: list[str],
    *,
    integration: str | None = None,
    limit: int = 20,
) -> list[ResolutionHit]:
    """Lookup durable resolutions for alias strings. Never raises."""
    norms = [normalize_alias(a) for a in aliases if normalize_alias(a)]
    if not org_id or not norms:
        return []
    try:
        query = (
            client.table(TABLE)
            .select("alias_normalized, entity_type, entity_id, integration, source, confidence")
            .eq("org_id", org_id)
            .in_("alias_normalized", norms[:50])
            .order("confidence", desc=True)
            .limit(limit)
        )
        if integration:
            query = query.eq("integration", str(integration).strip().lower())
        resp = query.execute()
        hits: list[ResolutionHit] = []
        for row in resp.data or []:
            hits.append(
                ResolutionHit(
                    alias_normalized=str(row.get("alias_normalized") or ""),
                    entity_type=str(row.get("entity_type") or ""),
                    entity_id=str(row.get("entity_id") or ""),
                    integration=str(row.get("integration") or ""),
                    source=str(row.get("source") or "org entity cache"),
                    confidence=float(row.get("confidence") or 0.0),
                )
            )
        return hits
    except Exception as exc:  # noqa: BLE001
        logger.debug("entity_resolution_lookup_skipped org_id=%s error=%s", org_id, exc)
        return []


def promote_from_session(
    client: Any,
    *,
    org_id: str,
    session: Any,
    integration: str,
    entity_id: str | None,
    structured: dict[str, Any] | None,
    conversation_id: str | None = None,
    source: str = "tool_output",
    confidence: float = 0.85,
) -> int:
    """Promote session entity attributes + ids into durable resolution rows."""
    if not client or not org_id:
        return 0
    written = 0
    attrs = dict(structured or {})
    eid = str(entity_id or "").strip()

    if hasattr(session, "active_entities"):
        for entity in (session.active_entities or {}).values():
            if not isinstance(entity, dict):
                continue
            if str(entity.get("integration") or "").lower() != str(integration or "").lower():
                continue
            nested = entity.get("attributes")
            if isinstance(nested, dict):
                for k, v in nested.items():
                    attrs.setdefault(k, v)
            nested_id = entity.get("entityId") or entity.get("entity_id")
            if nested_id and not eid:
                eid = str(nested_id).strip()

    # name / email aliases → entity_id when known
    if eid and attrs.get("name"):
        if upsert_resolution(
            client,
            org_id=org_id,
            alias=str(attrs["name"]),
            entity_type="named_entity",
            entity_id=eid,
            integration=integration,
            source=source,
            confidence=confidence,
            conversation_id=conversation_id,
        ):
            written += 1
    if eid and attrs.get("email"):
        if upsert_resolution(
            client,
            org_id=org_id,
            alias=str(attrs["email"]),
            entity_type="contact",
            entity_id=eid,
            integration=integration,
            source=source,
            confidence=confidence,
            conversation_id=conversation_id,
        ):
            written += 1

    for attr_key, entity_type in _ATTR_ENTITY_TYPES.items():
        value = attrs.get(attr_key)
        if value in (None, ""):
            continue
        value_s = str(value).strip()
        if attr_key in {"contact_id", "company_id", "list_id"}:
            if upsert_resolution(
                client,
                org_id=org_id,
                alias=value_s,
                entity_type=entity_type,
                entity_id=value_s,
                integration=integration,
                source=source,
                confidence=confidence,
                conversation_id=conversation_id,
            ):
                written += 1
            if attrs.get("name"):
                if upsert_resolution(
                    client,
                    org_id=org_id,
                    alias=str(attrs["name"]),
                    entity_type=entity_type,
                    entity_id=value_s,
                    integration=integration,
                    source=source,
                    confidence=confidence,
                    conversation_id=conversation_id,
                ):
                    written += 1
    return written


def org_bindings_for_candidates(
    client: Any,
    org_id: str,
    *,
    integration: str | None,
    candidates_by_arg: dict[str, tuple[str, ...]],
    hint_aliases: list[str] | None = None,
) -> dict[str, tuple[str, str]]:
    """Return arg_key → (value, source_label) from durable resolutions."""
    aliases: list[str] = list(hint_aliases or [])
    for candidates in candidates_by_arg.values():
        aliases.extend(candidates)
    hits = lookup_resolutions(client, org_id, aliases, integration=integration)
    if not hits:
        return {}
    by_alias = {h.alias_normalized: h for h in hits}
    bindings: dict[str, tuple[str, str]] = {}
    for arg_key, candidates in candidates_by_arg.items():
        for candidate in candidates:
            hit = by_alias.get(normalize_alias(candidate))
            if hit and hit.entity_id:
                bindings[arg_key] = (hit.entity_id, "org entity cache")
                break
        if arg_key not in bindings and hint_aliases:
            for hint in hint_aliases:
                hit = by_alias.get(normalize_alias(hint))
                if hit and hit.entity_id:
                    bindings[arg_key] = (hit.entity_id, "org entity cache")
                    break
    return bindings
