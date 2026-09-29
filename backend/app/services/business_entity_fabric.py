"""2.0-B — tenant-scoped BusinessEntity join fabric.

Joins provider bindings (HubSpot company, QBO customer, Zendesk org, GA4/GSC website)
only with explicit evidence and confidence. Never silent-merge below threshold.
Person joins are exact alias/email only (Memory HMAC exactness; no fuzzy names).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import uuid4

from app.services.entity_resolution_store import normalize_alias, upsert_resolution
from app.services.org_business_identity import normalize_host

JOIN_CONFIDENCE_THRESHOLD = 0.85

JoinStatus = Literal[
    "joined",
    "created",
    "refused_low_confidence",
    "refused_ambiguous",
    "refused_cross_org",
    "refused_kind_mismatch",
]


@dataclass(frozen=True)
class EntityEvidence:
    kind: str
    value: str
    source: str


@dataclass(frozen=True)
class EntityBinding:
    system: str
    resource_type: str
    resource_id: str
    confidence: float
    evidence: tuple[EntityEvidence, ...] = ()


@dataclass(frozen=True)
class BusinessEntity:
    id: str
    org_id: str
    display_name: str
    kind: str
    bindings: tuple[EntityBinding, ...] = ()
    evidence: tuple[EntityEvidence, ...] = ()
    confidence: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "display_name": self.display_name,
            "kind": self.kind,
            "confidence": self.confidence,
            "bindings": [
                {
                    "system": b.system,
                    "resource_type": b.resource_type,
                    "resource_id": b.resource_id,
                    "confidence": b.confidence,
                    "evidence": [
                        {"kind": e.kind, "value": e.value, "source": e.source} for e in b.evidence
                    ],
                }
                for b in self.bindings
            ],
            "evidence": [
                {"kind": e.kind, "value": e.value, "source": e.source} for e in self.evidence
            ],
        }


@dataclass(frozen=True)
class JoinDecision:
    status: JoinStatus
    entity: BusinessEntity | None = None
    reason: str = ""


def _norm_email(value: str) -> str:
    return str(value or "").strip().lower()


def _norm_name(value: str) -> str:
    return normalize_alias(value)


def website_entity_from_identity(
    *,
    org_id: str,
    identity: dict[str, Any],
    ga4_property_id: str | None = None,
    gsc_site_url: str | None = None,
) -> BusinessEntity | None:
    """Project a website BusinessEntity from tenant identity + unique bindings."""
    host = str(identity.get("host") or normalize_host(str(identity.get("website") or "")))
    if not org_id or not host:
        return None
    evidence = (
        EntityEvidence(kind="host", value=host, source=str(identity.get("source") or "identity")),
    )
    bindings: list[EntityBinding] = []
    if ga4_property_id:
        bindings.append(
            EntityBinding(
                system="google_analytics",
                resource_type="property",
                resource_id=str(ga4_property_id),
                confidence=0.9,  # confidence-honesty-ok: unique host bind prior, not user-facing
                evidence=evidence,
            )
        )
    if gsc_site_url:
        bindings.append(
            EntityBinding(
                system="google_search_console",
                resource_type="site",
                resource_id=str(gsc_site_url),
                confidence=0.9,  # confidence-honesty-ok: unique host bind prior, not user-facing
                evidence=evidence,
            )
        )
    return BusinessEntity(
        id=f"website:{org_id}:{host}",
        org_id=str(org_id),
        display_name=host,
        kind="website",
        bindings=tuple(bindings),
        evidence=evidence,
        confidence=0.9 if bindings else 0.7,  # confidence-honesty-ok: bind prior, not user-facing
    )


def join_provider_bindings(
    *,
    org_id: str,
    display_name: str,
    kind: str,
    left: EntityBinding,
    right: EntityBinding,
    extra_evidence: tuple[EntityEvidence, ...] = (),
    existing_left_entity_id: str | None = None,
    existing_right_entity_id: str | None = None,
    left_org_id: str | None = None,
    right_org_id: str | None = None,
) -> JoinDecision:
    """Join two provider records into one BusinessEntity or refuse."""
    if not org_id:
        return JoinDecision(status="refused_cross_org", reason="missing_org")
    if left_org_id and str(left_org_id) != str(org_id):
        return JoinDecision(status="refused_cross_org", reason="left_org_mismatch")
    if right_org_id and str(right_org_id) != str(org_id):
        return JoinDecision(status="refused_cross_org", reason="right_org_mismatch")
    if left.system == right.system and left.resource_id != right.resource_id:
        return JoinDecision(status="refused_ambiguous", reason="same_system_distinct_ids")
    conf = min(float(left.confidence), float(right.confidence))
    if conf < JOIN_CONFIDENCE_THRESHOLD:
        return JoinDecision(status="refused_low_confidence", reason="below_threshold")

    left_keys = _evidence_keys(left.evidence + extra_evidence)
    right_keys = _evidence_keys(right.evidence + extra_evidence)
    if kind == "person":
        if not _person_exact_match(left_keys, right_keys):
            return JoinDecision(status="refused_ambiguous", reason="person_not_exact")
    elif kind in {"company", "website"}:
        if not _org_exact_match(left_keys, right_keys, kind=kind):
            return JoinDecision(status="refused_ambiguous", reason="insufficient_exact_evidence")
    else:
        return JoinDecision(status="refused_kind_mismatch", reason="unsupported_kind")

    if (
        existing_left_entity_id
        and existing_right_entity_id
        and existing_left_entity_id != existing_right_entity_id
    ):
        return JoinDecision(status="refused_ambiguous", reason="already_bound_distinct_entities")

    entity_id = existing_left_entity_id or existing_right_entity_id or str(uuid4())
    status: JoinStatus = "joined" if (existing_left_entity_id or existing_right_entity_id) else "created"
    entity = BusinessEntity(
        id=entity_id,
        org_id=str(org_id),
        display_name=display_name,
        kind=kind,
        bindings=(left, right) if left.system != right.system else (left,),
        evidence=tuple(dict.fromkeys(left.evidence + right.evidence + extra_evidence)),
        confidence=conf,
    )
    return JoinDecision(status=status, entity=entity, reason="exact_evidence")


def fold_company_bindings(
    *,
    org_id: str,
    display_name: str,
    bindings: tuple[EntityBinding, ...] | list[EntityBinding],
) -> JoinDecision:
    """Join HubSpot/QBO/Zendesk (etc.) company rows on exact host/email evidence.

    STA-312 Option B (Cesar sole owner): no fuzzy person names. Company joins
    require shared host. Name-only is refused.
    """
    ordered = [b for b in bindings if b is not None]
    if len(ordered) < 2:
        return JoinDecision(status="refused_ambiguous", reason="need_two_systems")
    last = join_provider_bindings(
        org_id=org_id,
        display_name=display_name,
        kind="company",
        left=ordered[0],
        right=ordered[1],
    )
    if last.entity is None:
        return last
    entity = last.entity
    for nxt in ordered[2:]:
        nxt_join = join_provider_bindings(
            org_id=org_id,
            display_name=display_name,
            kind="company",
            left=entity.bindings[0],
            right=nxt,
            extra_evidence=entity.evidence,
            existing_left_entity_id=entity.id,
        )
        if nxt_join.entity is None:
            return nxt_join
        merged = list(entity.bindings)
        if not any(b.system == nxt.system and b.resource_id == nxt.resource_id for b in merged):
            merged.append(nxt)
        entity = BusinessEntity(
            id=entity.id,
            org_id=entity.org_id,
            display_name=display_name,
            kind="company",
            bindings=tuple(merged),
            evidence=tuple(dict.fromkeys(entity.evidence + nxt_join.entity.evidence)),
            confidence=min(entity.confidence, nxt.confidence),
        )
        last = JoinDecision(status="joined", entity=entity, reason="exact_evidence")
    return last


def _is_uuid(value: str) -> bool:
    try:
        from uuid import UUID

        UUID(str(value))
        return True
    except (TypeError, ValueError):
        return False


def persist_join_store(client: Any, entity: BusinessEntity) -> int:
    """Write accepted joins to org_business_entities. Never raises. No-op for non-uuid org ids."""
    if client is None or not _is_uuid(entity.org_id):
        return 0
    try:
        evidence = [{"kind": e.kind, "value": e.value, "source": e.source} for e in entity.evidence]
        upserted = (
            client.table("org_business_entities")
            .upsert(
                {
                    "org_id": entity.org_id,
                    "canonical_key": entity.id[:200],
                    "display_name": entity.display_name[:200],
                    "kind": entity.kind,
                    "confidence": float(entity.confidence),
                    "evidence": evidence,
                },
                on_conflict="org_id,canonical_key",
            )
            .execute()
        )
        rows = upserted.data if isinstance(getattr(upserted, "data", None), list) else []
        row_id = str((rows[0] or {}).get("id") or "") if rows else ""
        written = 1 if rows else 0
        if not row_id:
            return written
        for binding in entity.bindings:
            client.table("org_business_entity_bindings").upsert(
                {
                    "org_id": entity.org_id,
                    "entity_id": row_id,
                    "system": binding.system,
                    "resource_type": binding.resource_type,
                    "resource_id": binding.resource_id,
                    "confidence": float(binding.confidence),
                    "evidence": [
                        {"kind": e.kind, "value": e.value, "source": e.source} for e in binding.evidence
                    ],
                },
                on_conflict="org_id,system,resource_type,resource_id",
            ).execute()
            written += 1
        return written
    except Exception:  # noqa: BLE001
        return 0


def _evidence_from_json(raw: Any) -> tuple[EntityEvidence, ...]:
    rows = raw if isinstance(raw, list) else []
    out: list[EntityEvidence] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()
        value = str(item.get("value") or "").strip()
        if not kind or not value:
            continue
        out.append(EntityEvidence(kind=kind, value=value, source=str(item.get("source") or "")))
    return tuple(out)


def load_accepted_entities(client: Any, org_id: str) -> list[BusinessEntity]:
    """Load tenant-scoped accepted joins. Empty if the store is missing."""
    if client is None or not org_id:
        return []
    try:
        ents = (
            client.table("org_business_entities")
            .select("id,org_id,canonical_key,display_name,kind,confidence,evidence")
            .eq("org_id", org_id)
            .limit(20)
            .execute()
        )
        rows = ents.data if isinstance(getattr(ents, "data", None), list) else []
        binds = (
            client.table("org_business_entity_bindings")
            .select("entity_id,system,resource_type,resource_id,confidence,evidence")
            .eq("org_id", org_id)
            .limit(80)
            .execute()
        )
        bind_rows = binds.data if isinstance(getattr(binds, "data", None), list) else []
    except Exception:  # noqa: BLE001
        return []
    by_id: dict[str, list[EntityBinding]] = {}
    for row in bind_rows:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("entity_id") or "")
        by_id.setdefault(eid, []).append(
            EntityBinding(
                system=str(row.get("system") or ""),
                resource_type=str(row.get("resource_type") or ""),
                resource_id=str(row.get("resource_id") or ""),
                confidence=float(row.get("confidence") or 0),
                evidence=_evidence_from_json(row.get("evidence")),
            )
        )
    out: list[BusinessEntity] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        eid = str(row.get("id") or "")
        canonical = str(row.get("canonical_key") or eid)
        out.append(
            BusinessEntity(
                id=canonical or eid,
                org_id=str(row.get("org_id") or org_id),
                display_name=str(row.get("display_name") or ""),
                kind=str(row.get("kind") or "company"),
                bindings=tuple(by_id.get(eid, [])),
                evidence=_evidence_from_json(row.get("evidence")),
                confidence=float(row.get("confidence") or 0),
            )
        )
    return out


def load_accepted_entity_for_vendors(
    client: Any,
    org_id: str,
    vendors: list[str] | None,
) -> BusinessEntity | None:
    wanted = {str(v).strip().lower() for v in (vendors or []) if str(v).strip()}
    entities = load_accepted_entities(client, org_id)
    if not entities:
        return None
    ranked = sorted(
        entities,
        key=lambda ent: len({b.system.strip().lower() for b in ent.bindings} & wanted),
        reverse=True,
    )
    return ranked[0]


def persist_business_entity(client: Any, entity: BusinessEntity) -> int:
    """Store accepted joins in the 2.0-B table plus alias projection. Never raises."""
    written = persist_join_store(client, entity)
    for binding in entity.bindings:
        if upsert_resolution(
            client,
            org_id=entity.org_id,
            alias=f"{binding.system}:{binding.resource_id}",
            entity_type="business_entity",
            entity_id=entity.id,
            integration=binding.system,
            source="business_entity_fabric",
            confidence=binding.confidence,
        ):
            written += 1
        if upsert_resolution(
            client,
            org_id=entity.org_id,
            alias=entity.id,
            entity_type="business_entity",
            entity_id=binding.resource_id,
            integration=binding.system,
            source="business_entity_fabric",
            confidence=binding.confidence,
        ):
            written += 1
    return written


def _evidence_keys(evidence: tuple[EntityEvidence, ...]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for item in evidence:
        key = str(item.kind or "").strip().lower()
        value = str(item.value or "").strip()
        if key == "host":
            value = normalize_host(value)
        elif key == "email":
            value = _norm_email(value)
        elif key in {"legal_name", "name", "display_name"}:
            value = _norm_name(value)
        if not key or not value:
            continue
        out.setdefault(key, set()).add(value)
    return out


def _person_exact_match(left: dict[str, set[str]], right: dict[str, set[str]]) -> bool:
    # STA-312: email/alias exact only. Display names are never identity proof.
    if left.get("email") and right.get("email") and left["email"] & right["email"]:
        return True
    return False


def _org_exact_match(
    left: dict[str, set[str]],
    right: dict[str, set[str]],
    *,
    kind: str,
) -> bool:
    if left.get("host") and right.get("host") and left["host"] & right["host"]:
        return True
    if kind == "company" and left.get("email") and right.get("email") and left["email"] & right["email"]:
        return True
    name_l = left.get("legal_name") or left.get("name") or left.get("display_name") or set()
    name_r = right.get("legal_name") or right.get("name") or right.get("display_name") or set()
    if name_l and name_r and name_l & name_r and left.get("host") and right.get("host") and left["host"] & right["host"]:
        return True
    if name_l and name_r and name_l & name_r and not (left.get("host") or right.get("host")):
        # Name-only is not enough — would be a silent merge.
        return False
    return False
