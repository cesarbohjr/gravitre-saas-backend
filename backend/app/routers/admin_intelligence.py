"""Admin intelligence dashboard API (v2 observability + v3 knowledge intelligence)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin
from app.config import Settings, get_settings
from app.services.knowledge_intelligence_service import load_admin_intelligence_snapshot
from app.services.response_evaluation_service import load_admin_response_evaluations
from app.services.entity_relationship_service import (
    list_relationships_for_entity,
    load_entity_relationships_snapshot,
)
from app.services.outcome_attribution_service import get_outcome_attribution_service
from app.services.company_intelligence_orchestrator import get_company_intelligence_orchestrator
from app.services.intelligence_engine_settings import (
    load_intelligence_engine_settings,
    save_intelligence_engine_settings,
    PERFORMANCE_MODES,
)
from app.services.performance_dashboard_service import load_performance_dashboard
from app.services.business_impact_service import load_business_impact_snapshot
from app.services.outcome_learning_service import get_outcome_learning_service
from app.services.intelligence_evaluation_service import get_intelligence_evaluation_service
from app.services.simulation_service import get_simulation_service
from app.services.training_signal_service import get_training_signal_service
from app.services.ai_trust_layer import get_ai_trust_layer

router = APIRouter(prefix="/api/admin/intelligence", tags=["intelligence-admin"])


@router.get("/learning-progress")
async def get_learning_progress(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
) -> dict[str, Any]:
    """Usage counts vs company-intelligence thresholds (honest new-org progress)."""
    return await get_company_intelligence_orchestrator().get_learning_progress(org_id)


@router.get("/snapshot")
async def get_intelligence_snapshot(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Org-scoped intelligence snapshot for the admin dashboard."""
    return await load_admin_intelligence_snapshot(settings, org_id)


@router.get("/relationships")
async def get_entity_relationships(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    entity_type: str | None = Query(default=None, alias="entityType"),
    entity_id: str | None = Query(default=None, alias="entityId"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    if entity_type and entity_id:
        return await list_relationships_for_entity(
            org_id, entity_type, entity_id, settings=settings
        )
    return await load_entity_relationships_snapshot(org_id, settings=settings, limit=limit)


@router.get("/evaluations")
async def get_response_evaluations(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    since_days: int | None = Query(default=None, ge=1, le=365, alias="sinceDays"),
) -> dict[str, Any]:
    """Org-scoped v7 response evaluations and retrieval ranker status."""
    return await load_admin_response_evaluations(
        settings,
        org_id,
        limit=limit,
        offset=offset,
        since_days=since_days,
    )


@router.get("/outcomes")
async def get_outcome_summaries(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    period_days: int = Query(default=7, ge=1, le=90, alias="periodDays"),
) -> dict[str, Any]:
    """v8 correlational outcomes plus unified intelligence outcome events."""
    service = get_outcome_attribution_service(settings)
    v8 = await service.load_admin_outcomes_snapshot(org_id, settings=settings)
    unified = await get_outcome_learning_service(settings).load_admin_outcomes_summary(
        org_id, period_days=period_days
    )
    return {"v8_outcome_attribution": v8, **unified}


@router.get("/evaluations/intelligence")
async def get_intelligence_evaluations(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    period_days: int = Query(default=7, ge=1, le=90, alias="periodDays"),
) -> dict[str, Any]:
    return await get_intelligence_evaluation_service(settings).load_admin_evaluations_summary(
        org_id, period_days=period_days
    )


@router.get("/routing")
async def get_routing_summary(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(settings)
    events = await get_outcome_learning_service(settings)._fetch_events(org_id)
    model_distribution: dict[str, int] = {}
    confidence_bands: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "insufficient": 0}
    confidences: list[float] = []
    escalations = 0
    trust = get_ai_trust_layer()
    for row in events:
        model = str(row.get("model_name") or "unknown")
        model_distribution[model] = model_distribution.get(model, 0) + 1
        score = row.get("confidence_score")
        if score is not None:
            confidences.append(float(score))
            band = trust.confidence_band(float(score))
            confidence_bands[band] = confidence_bands.get(band, 0) + 1
        if row.get("outcome_event") == "approval_required":
            escalations += 1
    guardrail_count = 0
    try:
        guard = (
            client.table("guardrail_events")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .execute()
        )
        guardrail_count = int(guard.count or 0)
    except Exception:  # noqa: BLE001
        pass
    return {
        "routing_decisions_24h": len(events),
        "escalations_to_human": escalations + guardrail_count,
        "model_distribution": model_distribution,
        "confidence_band_distribution": confidence_bands,
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
    }


@router.get("/simulations")
async def get_simulations_summary(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_simulation_service(settings).load_admin_simulations_summary(org_id)


@router.get("/trust-summary")
async def get_trust_summary(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    period_days: int = Query(default=7, ge=1, le=90, alias="periodDays"),
) -> dict[str, Any]:
    events = await get_outcome_learning_service(settings)._fetch_events(org_id)
    confidences = [float(r["confidence_score"]) for r in events if r.get("confidence_score") is not None]
    trust = get_ai_trust_layer()
    low = sum(1 for c in confidences if trust.confidence_band(c) in {"low", "insufficient"})
    advisory = sum(1 for r in events if r.get("outcome_event") == "recommendation_created")
    return {
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "low_confidence_rate": round(low / len(confidences), 4) if confidences else None,
        "missing_context_rate": None,
        "advisory_only_rate": round(advisory / max(len(events), 1), 4),
        "sources_cited_rate": None,
        "period_days": period_days,
    }


@router.get("/training-readiness")
async def get_training_readiness(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_training_signal_service(settings).get_training_readiness(org_id)


class IntelligenceEngineSettingsUpdate(BaseModel):
    validation_enabled: bool | None = None
    reranking_enabled: bool | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    max_chunks: int | None = Field(default=None, ge=1, le=50)
    connector_timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    performance_mode: str | None = None


class PerformanceModeUpdate(BaseModel):
    mode: str = Field(..., pattern="^(speed_priority|balanced|accuracy_priority)$")


@router.get("/engine-settings")
async def get_engine_settings(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    current = await load_intelligence_engine_settings(org_id, settings)
    return {
        "validationEnabled": current.validation_enabled,
        "rerankingEnabled": current.reranking_enabled,
        "confidenceThreshold": current.confidence_threshold,
        "maxChunks": current.max_chunks,
        "connectorTimeoutSeconds": current.connector_timeout_seconds,
        "performanceMode": current.performance_mode,
    }


@router.patch("/engine-settings")
async def update_engine_settings(
    body: IntelligenceEngineSettingsUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    payload = body.model_dump(exclude_none=True)
    saved = await save_intelligence_engine_settings(org_id, settings, payload)
    return {
        "validationEnabled": saved.validation_enabled,
        "rerankingEnabled": saved.reranking_enabled,
        "confidenceThreshold": saved.confidence_threshold,
        "maxChunks": saved.max_chunks,
        "connectorTimeoutSeconds": saved.connector_timeout_seconds,
        "performanceMode": saved.performance_mode,
    }


@router.get("/performance-mode")
async def get_performance_mode(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    current = await load_intelligence_engine_settings(org_id, settings)
    return {"mode": current.performance_mode}


@router.patch("/performance-mode")
async def update_performance_mode(
    body: PerformanceModeUpdate,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    if body.mode not in PERFORMANCE_MODES:
        return {"mode": "balanced"}
    saved = await save_intelligence_engine_settings(org_id, settings, {"performance_mode": body.mode})
    return {"mode": saved.performance_mode}


@router.get("/business-impact")
async def get_business_impact_snapshot(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Revenue Risk Radar + Business Impact Score over existing v8/v10 signals."""
    return await load_business_impact_snapshot(org_id, settings=settings)


@router.get("/performance")
async def get_performance_dashboard(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
    period: str = Query(default="24h", pattern="^(1h|24h|7d)$"),
) -> dict[str, Any]:
    return await load_performance_dashboard(settings, org_id, period=period)


@router.get("/knowledge-graph")
async def get_knowledge_graph_admin(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.services.knowledge_graph_service import get_knowledge_graph_service

    return await get_knowledge_graph_service().get_admin_summary(org_id, settings=settings)


@router.get("/process-mining")
async def get_process_mining_admin(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.services.process_mining_service import get_process_mining_service

    return await get_process_mining_service(settings).get_process_intelligence_summary(org_id)


@router.get("/world-model-status")
async def get_world_model_status_admin(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
) -> dict[str, Any]:
    from app.ml.world_models import WorldModelScaffold

    return await WorldModelScaffold().check_activation_status(org_id)


@router.get("/research-monitors")
async def get_research_monitors_admin(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from app.services.research_service import get_research_service
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(settings)
    try:
        rows = (
            client.table("research_monitors")
            .select("*")
            .eq("org_id", org_id)
            .eq("enabled", True)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    topics = [str(r.get("topic") or "") for r in rows]
    trending = []
    research = get_research_service(settings)
    for topic in topics[:5]:
        trending.extend(await research.detect_trends(org_id, topic))
    return {
        "active_monitors": len(rows),
        "topics": topics,
        "last_findings_summary": [
            {"topic": r.get("topic"), "lastCheckedAt": r.get("last_checked_at")} for r in rows[:10]
        ],
        "trending_topics": trending[:10],
        "advisory_only": True,
    }


@router.get("/consensus-history")
async def get_consensus_history_admin(
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    from datetime import datetime, timedelta, timezone
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(settings)
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    try:
        rows = (
            client.table("intelligence_consensus_deliberations")
            .select("*")
            .eq("org_id", org_id)
            .gte("created_at", since)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
            .data
            or []
        )
    except Exception:
        rows = []
    recent = [
        {
            "recommendation_summary": r.get("recommendation_summary"),
            "confidence": r.get("confidence"),
            "vote_breakdown": r.get("vote_breakdown") or {},
            "minority_opinions": r.get("minority_opinions") or [],
            "timestamp": r.get("created_at"),
        }
        for r in rows
    ]
    confidences = [float(r.get("confidence") or 0) for r in rows if r.get("confidence") is not None]
    return {
        "recent_deliberations": recent,
        "consensus_trigger_rate_7d": round(len(rows) / 7.0, 4),
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "advisory_only": True,
    }
