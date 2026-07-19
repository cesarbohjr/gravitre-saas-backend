"""v6 entity relationship builder — restates existing v3/v4 signal only.

Module C / STA-331: stored edge ``confidence`` values written here are
**heuristic estimates** (``confidence_source=entity_relationship_heuristic``),
not learned scores. Knowledge-graph scoring blends these with type reliability
priors that are *also* estimates — see ``KG_BLEND_NOTE`` in confidence_honesty.
The blend is not more authoritative than either input alone.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.confidence_honesty import (
    CONFIDENCE_SOURCE_EDGE_HEURISTIC,
    estimated_confidence,
)
from app.services.query_normalization import normalize_query
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


def _heuristic_edge_confidence(value: float) -> float:
    """DB stores a float; provenance is always entity_relationship_heuristic estimate."""
    return float(estimated_confidence(value, source=CONFIDENCE_SOURCE_EDGE_HEURISTIC)["confidence"])

REL_ASSOCIATED_DEPARTMENT = "associated-department"
REL_REFERENCED_BY_AGENT = "referenced-by-agent"
REL_COOCCURS_WITH = "co-occurs-with"

ENTITY_GLOSSARY = "glossary_term"
ENTITY_DEPARTMENT = "department"
ENTITY_AGENT = "agent"
ENTITY_QUERY_CLUSTER = "query_cluster"
ENTITY_WORKFLOW_RUN = "workflow_run"

# Connector-sourced business entities (v6 extension — same soft-reference table)
ENTITY_CUSTOMER = "customer"
ENTITY_LEAD = "lead"
ENTITY_DEAL = "deal"
ENTITY_CAMPAIGN = "campaign"
ENTITY_SUPPORT_TICKET = "support_ticket"
ENTITY_INVOICE = "invoice"
ENTITY_PROJECT = "project"
ENTITY_EMPLOYEE = "employee"
ENTITY_VENDOR = "vendor"
ENTITY_PROSPECT = "prospect"
ENTITY_CONTACT = "contact"
ENTITY_MEETING = "meeting"
ENTITY_CONTRACT = "contract"
ENTITY_TASK = "task"
ENTITY_OBJECTIVE = "objective"
ENTITY_KPI = "kpi"

BUSINESS_ENTITY_TYPES = frozenset(
    {
        ENTITY_CUSTOMER,
        ENTITY_LEAD,
        ENTITY_DEAL,
        ENTITY_CAMPAIGN,
        ENTITY_SUPPORT_TICKET,
        ENTITY_INVOICE,
        ENTITY_PROJECT,
        ENTITY_EMPLOYEE,
        ENTITY_VENDOR,
        ENTITY_PROSPECT,
        ENTITY_CONTACT,
        ENTITY_MEETING,
        ENTITY_CONTRACT,
        ENTITY_TASK,
        ENTITY_OBJECTIVE,
        ENTITY_KPI,
    }
)

REL_TRACKED_BY = "tracked-by"
REL_OBSERVED_IN = "observed-in"
REL_BELONGS_TO = "belongs-to"
REL_INFLUENCED_BY = "influenced-by"
REL_REPORTS_TO = "reports_to"
REL_BLOCKED_BY = "blocked_by"
REL_CONTRIBUTES_TO = "contributes_to"
REL_IMPACTS = "impacts"
REL_REFERENCES = "references"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_department_id(client: Any, org_id: str, department_name: str) -> str:
    name = (department_name or "").strip()
    if not name:
        return ""
    rows = (
        client.table("departments")
        .select("id, name")
        .eq("org_id", org_id)
        .eq("name", name)
        .limit(1)
        .execute()
        .data
        or []
    )
    if rows:
        return str(rows[0]["id"])
    return normalize_query(name) or name.lower()


def _upsert_relationship(
    client: Any,
    *,
    org_id: str,
    source_entity_type: str,
    source_entity_id: str,
    relationship_type: str,
    target_entity_type: str,
    target_entity_id: str,
    confidence: float,
    evidence_count: int = 1,
) -> bool:
    if not source_entity_id or not target_entity_id:
        return False
    now = _now_iso()
    existing = (
        client.table("org_entity_relationships")
        .select("id, evidence_count")
        .eq("org_id", org_id)
        .eq("source_entity_type", source_entity_type)
        .eq("source_entity_id", source_entity_id)
        .eq("relationship_type", relationship_type)
        .eq("target_entity_type", target_entity_type)
        .eq("target_entity_id", target_entity_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if existing:
        row = existing[0]
        new_count = int(row.get("evidence_count") or 0) + evidence_count
        client.table("org_entity_relationships").update(
            {
                "evidence_count": new_count,
                "confidence": confidence,
                "last_observed_at": now,
            }
        ).eq("id", row["id"]).execute()
        return True

    client.table("org_entity_relationships").insert(
        {
            "org_id": org_id,
            "source_entity_type": source_entity_type,
            "source_entity_id": source_entity_id,
            "relationship_type": relationship_type,
            "target_entity_type": target_entity_type,
            "target_entity_id": target_entity_id,
            "confidence": confidence,
            "evidence_count": evidence_count,
            "last_observed_at": now,
            "created_at": now,
        }
    ).execute()
    return True


def _load_glossary_terms(client: Any, org_id: str) -> list[dict[str, Any]]:
    return (
        client.table("org_glossary_terms")
        .select("id, term, associated_department, frequency")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )


def _text_contains_term(text: str, term: str) -> bool:
    haystack = normalize_query(text)
    needle = normalize_query(term)
    if not haystack or not needle:
        return False
    if len(needle) <= 3:
        return f" {needle} " in f" {haystack} "
    return needle in haystack


async def build_relationships_from_glossary(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> int:
    """Restate org_glossary_terms.associated_department as glossary_term -> department edges."""
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    count = 0
    for row in _load_glossary_terms(db, org_id):
        dept = str(row.get("associated_department") or "").strip()
        if not dept:
            continue
        dept_id = _resolve_department_id(db, org_id, dept)
        if _upsert_relationship(
            db,
            org_id=org_id,
            source_entity_type=ENTITY_GLOSSARY,
            source_entity_id=str(row["id"]),
            relationship_type=REL_ASSOCIATED_DEPARTMENT,
            target_entity_type=ENTITY_DEPARTMENT,
            target_entity_id=dept_id,
            confidence=_heuristic_edge_confidence(0.8),
            evidence_count=max(1, int(row.get("frequency") or 1)),
        ):
            count += 1
    return count


async def build_relationships_from_agent_memories(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> int:
    """Link agents to glossary terms when active memory content mentions the term."""
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    glossary = _load_glossary_terms(db, org_id)
    if not glossary:
        return 0

    memories = (
        db.table("agent_memories")
        .select("id, agent_id, content, is_active")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    count = 0
    for memory in memories:
        if memory.get("is_active") is False:
            continue
        content = str(memory.get("content") or "")
        agent_id = str(memory.get("agent_id") or "")
        if not content or not agent_id:
            continue
        for term_row in glossary:
            term = str(term_row.get("term") or "")
            if not _text_contains_term(content, term):
                continue
            if _upsert_relationship(
                db,
                org_id=org_id,
                source_entity_type=ENTITY_AGENT,
                source_entity_id=agent_id,
                relationship_type=REL_REFERENCED_BY_AGENT,
                target_entity_type=ENTITY_GLOSSARY,
                target_entity_id=str(term_row["id"]),
                confidence=_heuristic_edge_confidence(0.6),
                evidence_count=1,
            ):
                count += 1
    return count


async def build_relationships_from_query_clusters(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> int:
    """Link query clusters to glossary terms mentioned in representative queries."""
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    glossary = _load_glossary_terms(db, org_id)
    if not glossary:
        return 0

    clusters = (
        db.table("org_query_clusters")
        .select("id, representative_queries")
        .eq("org_id", org_id)
        .execute()
        .data
        or []
    )
    count = 0
    for cluster in clusters:
        cluster_id = str(cluster.get("id") or "")
        reps = cluster.get("representative_queries") or []
        if isinstance(reps, str):
            reps = [reps]
        if not cluster_id or not reps:
            continue
        combined = " ".join(str(q) for q in reps)
        for term_row in glossary:
            term = str(term_row.get("term") or "")
            if not _text_contains_term(combined, term):
                continue
            if _upsert_relationship(
                db,
                org_id=org_id,
                source_entity_type=ENTITY_QUERY_CLUSTER,
                source_entity_id=cluster_id,
                relationship_type=REL_COOCCURS_WITH,
                target_entity_type=ENTITY_GLOSSARY,
                target_entity_id=str(term_row["id"]),
                confidence=_heuristic_edge_confidence(0.7),
                evidence_count=1,
            ):
                count += 1
    return count


async def build_relationships_from_crm_data(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> int:
    """
    Restate connector-observed CRM entities from v8 outcome baselines and marketing
    attribution rows — no new CRM polling/sync pipeline.
    """
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    rows = (
        db.table("agent_action_outcomes")
        .select("agent_id, workflow_run_id, target_entity_type, target_entity_id, action_type")
        .eq("org_id", org_id)
        .limit(5000)
        .execute()
        .data
        or []
    )
    count = 0
    seen: set[tuple[str, ...]] = set()
    for row in rows:
        entity_type = str(row.get("target_entity_type") or "").strip()
        entity_id = str(row.get("target_entity_id") or "").strip()
        if not entity_type or not entity_id:
            continue
        if entity_type not in BUSINESS_ENTITY_TYPES and entity_type not in {
            "subscription",
            "marketing_campaign",
            "hubspot_campaign",
            "linkedin_post",
            "canva_export",
        }:
            continue
        normalized_type = ENTITY_DEAL if entity_type == "subscription" else entity_type
        if normalized_type == "hubspot_campaign":
            normalized_type = ENTITY_CAMPAIGN
        elif normalized_type == "marketing_campaign":
            normalized_type = ENTITY_CAMPAIGN

        agent_id = str(row.get("agent_id") or "").strip()
        if agent_id:
            key = (normalized_type, entity_id, REL_TRACKED_BY, ENTITY_AGENT, agent_id)
            if key not in seen:
                seen.add(key)
                if _upsert_relationship(
                    db,
                    org_id=org_id,
                    source_entity_type=normalized_type,
                    source_entity_id=entity_id,
                    relationship_type=REL_TRACKED_BY,
                    target_entity_type=ENTITY_AGENT,
                    target_entity_id=agent_id,
                    confidence=_heuristic_edge_confidence(0.75),
                    evidence_count=1,
                ):
                    count += 1

        run_id = str(row.get("workflow_run_id") or "").strip()
        if run_id:
            key = (normalized_type, entity_id, REL_OBSERVED_IN, ENTITY_WORKFLOW_RUN, run_id)
            if key not in seen:
                seen.add(key)
                if _upsert_relationship(
                    db,
                    org_id=org_id,
                    source_entity_type=normalized_type,
                    source_entity_id=entity_id,
                    relationship_type=REL_OBSERVED_IN,
                    target_entity_type=ENTITY_WORKFLOW_RUN,
                    target_entity_id=run_id,
                    confidence=_heuristic_edge_confidence(0.7),
                    evidence_count=1,
                ):
                    count += 1

        action_type = str(row.get("action_type") or "")
        if normalized_type == ENTITY_CAMPAIGN and "linkedin" in action_type:
            post_id = entity_id
            key = (ENTITY_CAMPAIGN, post_id, REL_INFLUENCED_BY, "linkedin_post", post_id)
            if key not in seen:
                seen.add(key)
                if _upsert_relationship(
                    db,
                    org_id=org_id,
                    source_entity_type=ENTITY_CAMPAIGN,
                    source_entity_id=post_id,
                    relationship_type=REL_INFLUENCED_BY,
                    target_entity_type="linkedin_post",
                    target_entity_id=post_id,
                    confidence=_heuristic_edge_confidence(0.65),
                    evidence_count=1,
                ):
                    count += 1
    return count


async def rebuild_org_entity_relationships(
    org_id: str,
    *,
    settings: Settings | None = None,
    client: Any | None = None,
) -> dict[str, int]:
    """Rebuild all v6 relationships from existing v3/v4/v8 signal tables."""
    active_settings = settings or get_settings()
    db = client or get_supabase_client(active_settings)
    db.table("org_entity_relationships").delete().eq("org_id", org_id).execute()
    glossary_count = await build_relationships_from_glossary(org_id, settings=active_settings, client=db)
    memory_count = await build_relationships_from_agent_memories(org_id, settings=active_settings, client=db)
    cluster_count = await build_relationships_from_query_clusters(org_id, settings=active_settings, client=db)
    crm_count = await build_relationships_from_crm_data(org_id, settings=active_settings, client=db)
    summary = {
        "glossary_department": glossary_count,
        "agent_glossary": memory_count,
        "cluster_glossary": cluster_count,
        "crm_outcomes": crm_count,
        "total": glossary_count + memory_count + cluster_count + crm_count,
    }
    logger.info("entity_relationships_rebuilt org_id=%s summary=%s", org_id, summary)
    return summary
