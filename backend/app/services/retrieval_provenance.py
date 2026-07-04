"""Provenance envelopes for domain-aware retrieval results."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.domain_retrieval_policy import RetrievalPlan


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_provenance_envelope(
    *,
    source_system: str,
    source_name: str,
    source_type: str,
    source_id: str | None = None,
    assignment_id: str | None = None,
    last_updated: str | None = None,
    freshness_score: float | None = None,
    permission_scope: str | None = None,
    confidence: float | None = None,
    reference_only: bool = True,
    plan: RetrievalPlan | None = None,
    match_tier: str | None = None,
    weight_applied: float | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_plan = plan or RetrievalPlan(active=False)
    envelope = {
        "source_system": source_system,
        "source_name": source_name,
        "source_type": source_type,
        "source_id": source_id,
        "assignment_id": assignment_id,
        "retrieved_at": _now_iso(),
        "last_updated": last_updated,
        "freshness_score": freshness_score,
        "permission_scope": permission_scope or "org_member",
        "confidence": confidence,
        "reference_only": reference_only,
        "retrieval_policy": active_plan.policy_version if active_plan.active else "legacy",
        "domain_department": active_plan.domain_department,
        "domain_subdomain": active_plan.domain_subdomain,
        "match_tier": match_tier,
        "weight_applied": weight_applied,
    }
    if extra:
        envelope.update(extra)
    return envelope


def build_from_rag_row(
    row: dict[str, Any],
    *,
    plan: RetrievalPlan | None = None,
    match_tier: str | None = None,
) -> dict[str, Any]:
    meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
    score = float(row.get("score") or 0.0)
    return build_provenance_envelope(
        source_system=str(meta.get("source_system") or meta.get("connector") or "rag"),
        source_name=str(row.get("title") or row.get("source") or meta.get("source_title") or "Knowledge"),
        source_type=str(meta.get("source_type") or "rag_chunk"),
        source_id=str(row.get("document_id") or meta.get("source_id") or row.get("id") or ""),
        assignment_id=str(meta.get("assignment_id") or meta.get("assignmentId") or row.get("assignment_id") or "") or None,
        last_updated=str(meta.get("last_updated") or meta.get("source_updated_at") or "") or None,
        freshness_score=float(meta.get("freshness_score") or row.get("freshness_score") or 0.75),
        confidence=score,
        reference_only=bool(meta.get("reference_only", True)),
        plan=plan,
        match_tier=match_tier,
        weight_applied=score,
    )


def build_from_memory_row(row: dict[str, Any], *, plan: RetrievalPlan | None = None) -> dict[str, Any]:
    return build_provenance_envelope(
        source_system="gravitre",
        source_name=str(row.get("title") or row.get("label") or row.get("memory_type") or "Agent memory"),
        source_type=str(row.get("memory_type") or row.get("category") or "agent_memory"),
        source_id=str(row.get("id") or ""),
        confidence=float(row.get("score") or row.get("relevance") or 0.7),
        reference_only=True,
        plan=plan,
        match_tier="memory",
    )


def build_from_graph_context(graph: dict[str, Any], *, plan: RetrievalPlan | None = None) -> dict[str, Any]:
    return build_provenance_envelope(
        source_system="gravitre",
        source_name=str(graph.get("summary") or graph.get("entity") or "Knowledge graph"),
        source_type="knowledge_graph",
        source_id=str(graph.get("entity_id") or graph.get("id") or ""),
        confidence=float(graph.get("confidence") or 0.75),
        reference_only=True,
        plan=plan,
        match_tier="graph",
        extra={"graph_context": True},
    )


def summarize_retrieval_effectiveness(
    sources: list[dict[str, Any]],
    *,
    plan: RetrievalPlan | None = None,
    classification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    domain = (classification or {}).get("domain") or {}
    top_sources = []
    assignment_ids: list[str] = []
    for row in sources[:8]:
        prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
        top_sources.append(
            {
                "source_name": prov.get("source_name") or row.get("title") or row.get("source"),
                "source_type": prov.get("source_type") or row.get("kind"),
                "assignment_id": prov.get("assignment_id"),
                "score": row.get("score"),
                "match_tier": prov.get("match_tier"),
            }
        )
        aid = prov.get("assignment_id")
        if aid and aid not in assignment_ids:
            assignment_ids.append(str(aid))
    scores = [float(row.get("score") or 0) for row in sources[:8] if row.get("score") is not None]
    retrieval_score = round(sum(scores) / len(scores), 4) if scores else None
    return {
        "retrieval_policy": (plan.policy_version if plan and plan.active else "legacy"),
        "domain_department": domain.get("department_key") or domain.get("department"),
        "domain_subdomain": domain.get("subdomain_key") or domain.get("subdomain"),
        "top_sources": top_sources,
        "assignment_ids_used": assignment_ids,
        "retrieval_score": retrieval_score,
        "source_count": len(sources),
    }
