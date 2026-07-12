"""User-facing intelligence engine capability endpoints."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.ml.model_catalog import build_ml_catalog_dashboard
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.explanation_generator import get_explanation_generator
from app.services.intelligence_router import get_intelligence_router
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.optimization_suggestion_service import get_optimization_suggestion_service
from app.services.outcome_tracker import get_outcome_tracker
from app.services.risk_approval_evaluator import get_risk_approval_evaluator
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.training_signal_service import get_training_signal_service
from app.workflows.audit import write_audit_event
from app.workflows.repository import get_supabase_client

router = APIRouter(prefix="/api/intelligence", tags=["intelligence-engine"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    mode: str = "standard"


class ExplainRequest(BaseModel):
    entity_type: str
    entity_id: str


class RecommendRequest(BaseModel):
    context: str = Field(..., min_length=1)


class ForecastRequest(BaseModel):
    metric: str = Field(..., min_length=1)
    horizon_days: int = Field(default=30, ge=1, le=365)


class OptimizeRequest(BaseModel):
    workflow_id: str | None = None


class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=1)


class ExecuteRequest(BaseModel):
    action_plan: dict[str, Any]
    approval_id: str | None = None


@router.post("/ask")
async def intelligence_ask(
    body: AskRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    user: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id = str(user[0].get("sub") or user[0].get("id") or "admin")
    return await get_intelligence_router(settings).route(
        org_id,
        user_id,
        body.question,
        surface="api_ask",
        mode=body.mode,
    )


@router.post("/explain")
async def intelligence_explain(
    body: ExplainRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    graph = await get_knowledge_graph_service().explain_entity(
        org_id,
        body.entity_type,
        body.entity_id,
        settings=settings,
    )
    explanation = await get_explanation_generator().explain(
        "answer",
        org_id,
        graph.get("businessSignals") or [],
        graph,
    )
    return {
        "explanation": explanation,
        "graph": graph,
        "advisory_only": True,
    }


@router.post("/recommend")
async def intelligence_recommend(
    body: RecommendRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    recs = await get_decision_intelligence_service(settings).recommend_next_action(org_id, body.context)
    primary = (recs.get("recommendations") or [{}])[0]
    return get_ai_trust_layer().wrap_response(
        answer=str(primary.get("action") or ""),
        sources=[{"type": "optimization_suggestions"}],
        confidence=float(primary.get("confidence") or 0.5),
        reasoning_summary=str(primary.get("reasoning") or ""),
        actions_taken=[],
        actions_pending_approval=[primary] if primary else [],
        advisory_only=True,
    )


@router.get("/recommendations/heuristics")
async def intelligence_heuristic_recommendations(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """STA-314 suggest-only heuristic cards — never invokes tools or write gates."""
    from app.services.recommendation_heuristics_service import (
        assert_no_execute_surface,
        build_heuristic_recommendations,
    )
    from app.workflows.repository import get_supabase_client

    client = get_supabase_client(settings)
    connected: list[dict[str, Any]] = []
    usage_by_connector: dict[str, int] = {}
    installed_packs: set[str] = set()

    try:
        connectors_res = (
            client.table("connectors")
            .select("id,vendor,status,display_name,auth_status")
            .eq("org_id", org_id)
            .execute()
        )
        for row in list(connectors_res.data or []):
            vendor = str(row.get("vendor") or "").strip().lower()
            if not vendor:
                continue
            status_value = str(row.get("status") or row.get("auth_status") or "").lower()
            connected.append(
                {
                    "vendor": vendor,
                    "label": row.get("display_name") or vendor,
                    "status": status_value or "connected",
                    "connected": True,
                    "executable": status_value not in {"error", "expired", "disconnected"},
                }
            )
    except Exception:
        connected = []

    try:
        packs_res = (
            client.table("org_department_pack_installs")
            .select("pack_id")
            .eq("org_id", org_id)
            .execute()
        )
        installed_packs = {
            str(row.get("pack_id") or "").strip()
            for row in list(packs_res.data or [])
            if row.get("pack_id")
        }
    except Exception:
        installed_packs = set()

    try:
        events_res = (
            client.table("audit_events")
            .select("metadata")
            .eq("org_id", org_id)
            .limit(500)
            .execute()
        )
        for row in list(events_res.data or []):
            meta = row.get("metadata") or {}
            if not isinstance(meta, dict):
                continue
            vendor = str(
                meta.get("connector")
                or meta.get("connector_type")
                or meta.get("vendor")
                or ""
            ).strip().lower()
            if vendor:
                usage_by_connector[vendor] = usage_by_connector.get(vendor, 0) + 1
    except Exception:
        usage_by_connector = {}

    payload = build_heuristic_recommendations(
        connected_connectors=connected,
        usage_by_connector=usage_by_connector,
        installed_packs=installed_packs,
    )
    assert_no_execute_surface(payload)
    return payload


@router.post("/forecast")
async def intelligence_forecast(
    body: ForecastRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_intelligence_router(settings).forecast(
        org_id,
        body.metric,
        horizon_days=body.horizon_days,
    )


@router.post("/optimize")
async def intelligence_optimize(
    body: OptimizeRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_intelligence_router(settings).optimize(org_id, body.workflow_id)


@router.post("/plan")
async def intelligence_plan(
    body: PlanRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    _admin: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    return await get_decision_intelligence_service(settings).scaffold_decision_plan(org_id, body.goal)


@router.post("/execute")
async def intelligence_execute(
    body: ExecuteRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    user: Annotated[tuple, Depends(require_admin)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    user_id = str(user[0].get("sub") or user[0].get("id") or "admin")
    from app.services.task_classifier import get_task_classifier

    classification = await get_task_classifier(settings).classify(
        org_id,
        str(body.action_plan.get("summary") or "execute action"),
    )
    persona = {"role": "operator", "requires_approval_for": ["all_actions"], "advisory_only": False}
    risk = await get_risk_approval_evaluator(settings).evaluate(
        org_id,
        user_id,
        body.action_plan,
        classification,
        persona,
    )
    if risk.get("requires_approval") and not body.approval_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="approval_id required before executing write actions",
        )
    client = get_supabase_client(settings)
    write_audit_event(
        client,
        org_id,
        user_id,
        "intelligence.execute.requested",
        "intelligence",
        org_id,
        metadata={"approval_id": body.approval_id, "action_plan": body.action_plan},
    )
    get_outcome_tracker(settings).track(
        org_id,
        None,
        None,
        body.action_plan,
        {"status": "queued_for_execution", "approval_id": body.approval_id},
        classification,
    )
    return {
        "status": "accepted",
        "approval_id": body.approval_id,
        "risk_evaluation": risk,
        "note": "Execution remains approval-gated; ToolRegistry invoked only after explicit approval.",
    }


@router.get("/models/catalog")
async def intelligence_models_catalog(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Org-scoped ML catalog for Intelligence Center (does not require admin)."""
    return await build_ml_catalog_dashboard(org_id, settings=settings)


@router.get("/training-readiness")
async def intelligence_training_readiness(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Training readiness signals for Intelligence Center model profiles."""
    return await get_training_signal_service(settings).get_training_readiness(org_id)
