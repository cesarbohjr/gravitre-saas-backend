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
    from app.services.confidence_honesty import (
        CONFIDENCE_SOURCE_HEURISTIC,
        CONFIDENCE_SOURCE_INSUFFICIENT,
        label_confidence,
    )

    recs = await get_decision_intelligence_service(settings).recommend_next_action(org_id, body.context)
    primary = (recs.get("recommendations") or [{}])[0]
    raw_conf = primary.get("confidence")
    if raw_conf is None:
        # Honest null — never invent 0.5 as a live intelligence score.
        labeled = label_confidence(None, source=CONFIDENCE_SOURCE_INSUFFICIENT)
        conf_value: float | None = None
        is_estimate = False
        source = CONFIDENCE_SOURCE_INSUFFICIENT
    else:
        labeled = label_confidence(
            float(raw_conf),
            source=str(primary.get("confidence_source") or CONFIDENCE_SOURCE_HEURISTIC),
            is_estimate=bool(primary.get("confidence_is_estimate", True)),
        )
        conf_value = labeled["confidence"]
        is_estimate = bool(labeled["confidence_is_estimate"])
        source = str(labeled["confidence_source"])
    return get_ai_trust_layer().wrap_response(
        answer=str(primary.get("action") or ""),
        sources=[{"type": "optimization_suggestions"}],
        confidence=conf_value,
        reasoning_summary=str(primary.get("reasoning") or ""),
        actions_taken=[],
        actions_pending_approval=[primary] if primary else [],
        advisory_only=True,
        confidence_is_estimate=is_estimate,
        confidence_source=source,
    )


@router.get("/recommendations/heuristics")
async def intelligence_heuristic_recommendations(
    org_id: Annotated[str, Depends(get_org_context)],
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """STA-314 suggest-only heuristic cards — never invokes tools or write gates."""
    from app.services.recommendation_heuristics_service import (
        assert_no_execute_surface,
        build_heuristic_recommendations,
        filter_dismissed_recommendations,
        load_dismissed_card_ids,
        load_heuristic_signals,
    )
    from app.workflows.repository import get_supabase_client

    user, _org, _role = member
    user_id = str(user.get("user_id") or user.get("sub") or "")
    client = get_supabase_client(settings)
    signals = load_heuristic_signals(client, org_id)
    payload = build_heuristic_recommendations(
        connected_connectors=signals["connected_connectors"],
        usage_by_connector=signals["usage_by_connector"],
        installed_packs=signals["installed_packs"],
        lookback_days=int(signals.get("lookback_days") or 30),
    )
    # CF — soft-rank after heuristics, before dismiss.
    # Prefers trained matrix factorization; falls back to item affinity.
    # Cold start when <50 scored interactions / 30d; never drops cards.
    try:
        from app.services.cf_rank_service import soft_rank_heuristic_payload_async

        payload = await soft_rank_heuristic_payload_async(
            client,
            org_id,
            payload,
            actor_id=user_id or None,
            settings=settings,
        )
    except Exception:  # noqa: BLE001
        payload = dict(payload)
        payload["cfRanked"] = False
        payload["cfMethod"] = "error"
    if user_id:
        payload = filter_dismissed_recommendations(
            payload,
            load_dismissed_card_ids(client, org_id, user_id),
        )
    # Phase 5.2 — outcome-informed ranking (advisory only; never executes; never drops cards).
    try:
        from app.services.recommendation_quality_engine import get_recommendation_quality_engine

        original = list(payload.get("recommendations") or [])
        ranked = await get_recommendation_quality_engine(settings).rank_recommendations(
            original,
            org_id=org_id,
            department="sales",
        )
        if ranked:
            ranked_ids = {str(c.get("id") or "") for c in ranked}
            for card in original:
                cid = str(card.get("id") or "")
                if cid and cid not in ranked_ids:
                    ranked.append(card)
            payload = dict(payload)
            payload["recommendations"] = ranked
            payload["outcomeRanked"] = True
        else:
            payload = dict(payload)
            payload["outcomeRanked"] = False
    except Exception:  # noqa: BLE001
        payload = dict(payload)
        payload["outcomeRanked"] = False
    assert_no_execute_surface(payload)
    return payload


@router.post("/recommendations/heuristics/{card_id}/dismiss")
async def intelligence_heuristic_dismiss(
    card_id: str,
    org_id: Annotated[str, Depends(get_org_context)],
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """STA-314 dismiss (STA-123 pattern) — advisory only; never executes tools."""
    from app.services.recommendation_heuristics_service import dismiss_heuristic_card
    from app.workflows.repository import get_supabase_client

    user, _org, _role = member
    user_id = str(user.get("user_id") or user.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User required")
    try:
        return dismiss_heuristic_card(
            get_supabase_client(settings),
            org_id,
            user_id,
            card_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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


@router.get("/churn-risk/advisory")
async def intelligence_churn_risk_advisory(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
    limit: int = 25,
) -> dict[str, Any]:
    """Suggest-only churn risk cards — never auto-contacts or invokes tools."""
    from app.services.churn_advisory_service import build_churn_advisory_cards

    return await build_churn_advisory_cards(org_id, settings=settings, limit=min(max(limit, 1), 100))


class ChurnLabelRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    features: dict[str, float] = Field(default_factory=dict)
    churned: bool | None = None
    label_reason: str | None = None


@router.post("/churn-risk/labels")
async def intelligence_churn_risk_label(
    body: ChurnLabelRequest,
    org_id: Annotated[str, Depends(get_org_context)],
    member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Upsert a labeled churn training example (FEATURE_KEYS contract)."""
    from app.ml.churn_feature_ingest import upsert_churn_training_example

    user, _org, _role = member
    actor_id = str(user.get("user_id") or user.get("sub") or "") or None
    client = get_supabase_client(settings)
    try:
        result = upsert_churn_training_example(
            client,
            org_id=org_id,
            customer_id=body.customer_id,
            features=body.features,
            churned=body.churned,
            label_reason=body.label_reason,
            agent_id=actor_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if actor_id:
        write_audit_event(
            client,
            org_id,
            actor_id,
            "churn.label.upserted",
            "churn_customer_signal",
            org_id,
            metadata={
                "customer_id": body.customer_id,
                "churned": result.get("churned"),
                "advisory_only": True,
            },
        )
    return result
