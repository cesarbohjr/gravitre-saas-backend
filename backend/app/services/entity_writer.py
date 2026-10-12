"""Phase 2E: runtime writer for the business entity store.

``persist_business_entity`` and the join rules in ``business_entity_fabric``
existed with no runtime caller, so the store only ever held fixtures. This
writer takes provider records (a HubSpot company, a Zendesk organisation, a
contact) and files each one, strongest evidence first:

1. provider id: the record is already bound, nothing to do;
2. exact host (companies) or exact email (people) matching exactly one stored
   entity: bind the record to it through ``join_provider_bindings``, which
   still refuses anything below the join threshold or ambiguous;
3. more than one candidate, or a join the rules refuse: record a proposed
   merge in ``org_entity_merge_proposals`` and bind nothing;
4. no candidate: create a new entity under a deterministic key
   (``company:host:<host>`` / ``person:email:<email>``) so two writers racing on
   the same record converge on one row.

Name-only records are never written (a name is not identity proof).

Off unless ENTITY_WRITER_ENABLED is true, and per org only when it opted in to
customer context for that vendor (source governance; fails closed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger
from app.services.business_entity_fabric import (
    JOIN_CONFIDENCE_THRESHOLD,
    BusinessEntity,
    EntityBinding,
    EntityEvidence,
    _evidence_from_json,
    join_provider_bindings,
    persist_business_entity,
)
from app.services.org_business_identity import normalize_host

logger = get_logger(__name__)

PROPOSALS_TABLE = "org_entity_merge_proposals"
RECORD_CONFIDENCE = 0.9  # provider record with exact host/email evidence


@dataclass(frozen=True)
class ProviderRecord:
    system: str
    resource_type: str
    resource_id: str
    display_name: str = ""
    kind: str = "company"  # company | person
    host: str = ""
    email: str = ""


@dataclass
class WriteResult:
    already_bound: int = 0
    joined: int = 0
    created: int = 0
    proposed: int = 0
    skipped_no_evidence: int = 0
    failed: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "already_bound": self.already_bound,
            "joined": self.joined,
            "created": self.created,
            "proposed": self.proposed,
            "skipped_no_evidence": self.skipped_no_evidence,
            "failed": self.failed,
        }


def _evidence(record: ProviderRecord) -> tuple[EntityEvidence, ...]:
    out: list[EntityEvidence] = []
    host = normalize_host(record.host) if record.host else ""
    email = record.email.strip().lower()
    if host:
        out.append(EntityEvidence(kind="host", value=host, source=record.system))
    if email:
        out.append(EntityEvidence(kind="email", value=email, source=record.system))
    if record.display_name:
        out.append(EntityEvidence(kind="legal_name", value=record.display_name, source=record.system))
    return tuple(out)


def _identity_key(record: ProviderRecord) -> tuple[str, str] | None:
    """(evidence kind, value) that may identify the record, or None."""
    if record.kind == "person":
        email = record.email.strip().lower()
        return ("email", email) if email else None
    host = normalize_host(record.host) if record.host else ""
    if host:
        return ("host", host)
    email = record.email.strip().lower()
    return ("email", email) if email else None


def _binding(record: ProviderRecord) -> EntityBinding:
    return EntityBinding(
        system=record.system.strip().lower(),
        resource_type=record.resource_type,
        resource_id=str(record.resource_id),
        confidence=RECORD_CONFIDENCE,
        evidence=_evidence(record),
    )


def _bound_entity_id(client: Any, org_id: str, b: EntityBinding) -> str | None:
    res = (
        client.table("org_business_entity_bindings")
        .select("entity_id")
        .eq("org_id", org_id)
        .eq("system", b.system)
        .eq("resource_type", b.resource_type)
        .eq("resource_id", b.resource_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return str(rows[0]["entity_id"]) if rows else None


def _candidates(client: Any, org_id: str, kind: str, key: tuple[str, str]) -> list[BusinessEntity]:
    ev_kind, value = key
    res = (
        client.table("org_business_entities")
        .select("id,org_id,canonical_key,display_name,kind,confidence,evidence")
        .eq("org_id", org_id)
        .eq("kind", kind)
        .contains("evidence", [{"kind": ev_kind, "value": value}])
        .limit(5)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return []
    ids = [str(r["id"]) for r in rows]
    binds = (
        client.table("org_business_entity_bindings")
        .select("entity_id,system,resource_type,resource_id,confidence,evidence")
        .eq("org_id", org_id)
        .in_("entity_id", ids)
        .execute()
    )
    by_id: dict[str, list[EntityBinding]] = {}
    for b in binds.data or []:
        by_id.setdefault(str(b.get("entity_id")), []).append(
            EntityBinding(
                system=str(b.get("system") or ""),
                resource_type=str(b.get("resource_type") or ""),
                resource_id=str(b.get("resource_id") or ""),
                confidence=float(b.get("confidence") or 0),
                evidence=_evidence_from_json(b.get("evidence")),
            )
        )
    return [
        BusinessEntity(
            id=str(r.get("canonical_key") or r["id"]),
            org_id=org_id,
            display_name=str(r.get("display_name") or ""),
            kind=str(r.get("kind") or kind),
            bindings=tuple(by_id.get(str(r["id"]), [])),
            evidence=_evidence_from_json(r.get("evidence")),
            confidence=float(r.get("confidence") or 0),
        )
        for r in rows
    ]


def _propose(
    client: Any,
    org_id: str,
    record: ProviderRecord,
    candidates: list[BusinessEntity],
    reason: str,
) -> None:
    client.table(PROPOSALS_TABLE).upsert(
        {
            "org_id": org_id,
            "kind": record.kind,
            "system": record.system.strip().lower(),
            "resource_type": record.resource_type,
            "resource_id": str(record.resource_id),
            "incoming": {
                "display_name": record.display_name,
                "host": normalize_host(record.host) if record.host else "",
                "email": record.email.strip().lower(),
            },
            "candidate_keys": [c.id for c in candidates],
            "reason": reason,
            "status": "proposed",
        },
        on_conflict="org_id,system,resource_type,resource_id",
        ignore_duplicates=True,
    ).execute()


def writer_enabled(settings: Any) -> bool:
    return getattr(settings, "entity_writer_enabled", False) is True


def write_provider_records(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    records: list[ProviderRecord],
) -> WriteResult:
    """File provider records into the entity store. Never raises per record."""
    from app.core.ingestion_kill_switch import ingestion_disabled
    from app.services.source_governance import (
        customer_context_allowed,
        load_source_governance,
    )

    result = WriteResult()
    if not writer_enabled(settings) or not records:
        return result
    if ingestion_disabled(settings):
        logger.warning("entity_writer_skipped org_id=%s reason=ingestion_disabled", org_id)
        return result
    try:
        policy = load_source_governance(client, org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("entity_writer_policy_unreadable org_id=%s error=%s", org_id, exc)
        return result
    for record in records:
        if not customer_context_allowed(policy, record.system):
            continue
        try:
            _write_one(client, org_id, record, result)
        except Exception as exc:  # noqa: BLE001
            result.failed += 1
            logger.warning(
                "entity_writer_record_failed org_id=%s system=%s error=%s", org_id, record.system, exc
            )
    if any((result.joined, result.created, result.proposed)):
        logger.info("entity_writer_done org_id=%s %s", org_id, result.as_dict())
    return result


def _write_one(client: Any, org_id: str, record: ProviderRecord, result: WriteResult) -> None:
    binding = _binding(record)
    if _bound_entity_id(client, org_id, binding):
        result.already_bound += 1
        return
    key = _identity_key(record)
    if key is None:
        result.skipped_no_evidence += 1
        return
    candidates = _candidates(client, org_id, record.kind, key)
    if len(candidates) > 1:
        _propose(client, org_id, record, candidates, "multiple_exact_matches")
        result.proposed += 1
        result.details.append({"resource_id": record.resource_id, "status": "proposed"})
        return
    if len(candidates) == 1:
        target = candidates[0]
        anchor = target.bindings[0] if target.bindings else EntityBinding(
            system="gravitre",
            resource_type="entity",
            resource_id=target.id,
            confidence=max(JOIN_CONFIDENCE_THRESHOLD, target.confidence),
            evidence=target.evidence,
        )
        same_system = [b for b in target.bindings if b.system == binding.system and b.resource_type == binding.resource_type]
        if same_system:
            # Already holds a different record from this system: two records, one host.
            _propose(client, org_id, record, candidates, "same_system_already_bound")
            result.proposed += 1
            return
        decision = join_provider_bindings(
            org_id=org_id,
            display_name=target.display_name or record.display_name,
            kind=record.kind,
            left=anchor,
            right=binding,
            extra_evidence=target.evidence,
            existing_left_entity_id=target.id,
        )
        if decision.entity is None:
            _propose(client, org_id, record, candidates, decision.reason or decision.status)
            result.proposed += 1
            return
        merged = BusinessEntity(
            id=target.id,
            org_id=org_id,
            display_name=target.display_name or record.display_name,
            kind=target.kind,
            bindings=(binding,),  # existing bindings are already stored
            evidence=tuple(dict.fromkeys(target.evidence + binding.evidence)),
            confidence=min(target.confidence or RECORD_CONFIDENCE, binding.confidence),
        )
        persist_business_entity(client, merged)
        result.joined += 1
        return
    entity = BusinessEntity(
        id=f"{record.kind}:{key[0]}:{key[1]}",
        org_id=org_id,
        display_name=record.display_name or key[1],
        kind=record.kind,
        bindings=(binding,),
        evidence=binding.evidence,
        confidence=binding.confidence,
    )
    persist_business_entity(client, entity)
    result.created += 1


def hubspot_company_records(payload: dict[str, Any]) -> list[ProviderRecord]:
    """Map a HubSpot companies list/search response to provider records."""
    out: list[ProviderRecord] = []
    for row in (payload or {}).get("results") or []:
        if not isinstance(row, dict) or not row.get("id"):
            continue
        props = row.get("properties") if isinstance(row.get("properties"), dict) else {}
        out.append(
            ProviderRecord(
                system="hubspot",
                resource_type="company",
                resource_id=str(row["id"]),
                display_name=str(props.get("name") or ""),
                kind="company",
                host=str(props.get("domain") or ""),
            )
        )
    return out
