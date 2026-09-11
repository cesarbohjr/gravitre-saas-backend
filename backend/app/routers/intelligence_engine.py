"""User-facing intelligence engine capability endpoints."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_org_context, require_admin, require_org_member
from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.ml.model_catalog import build_ml_catalog_dashboard
from app.services.decision_intelligence_service import get_decision_intelligence_service
from app.services.explanation_generator import get_explanation_generator
from app.services.intelligence_router import get_intelligence_router
from app.services.knowledge_graph_service import get_knowledge_graph_service
from app.services.memory_promotion_service import MemoryPromotionStatus, get_memory_promotion_service
from app.services.optimization_suggestion_service import get_optimization_suggestion_service
from app.services.outcome_learning_service import POSITIVE_EVENTS, get_outcome_learning_service
from app.services.outcome_tracker import get_outcome_tracker
from app.services.risk_approval_evaluator import get_risk_approval_evaluator
from app.services.ai_trust_layer import get_ai_trust_layer
from app.services.swarm_coordinator_service import SWARM_AGGREGATING, SWARM_RUNNING, list_swarm_runs
from app.services.training_signal_service import get_training_signal_service
from app.workflows.audit import write_audit_event
from app.workflows.constants import RUN_STATUS_PENDING_APPROVAL, RUN_TYPE_EXECUTE
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/intelligence", tags=["intelligence-engine"])

# Real outcome events that represent new inflow into a department (recommendation
# or prediction just created) — used only for Phase 2 Intelligence Core state.
_CORE_INFLOW_EVENTS = frozenset({"recommendation_created", "prediction_generated"})


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


@router.get("/core/state")
async def intelligence_core_state(
    org_id: Annotated[str, Depends(get_org_context)],
    _member: Annotated[tuple, Depends(require_org_member)],
    settings: Settings = Depends(get_settings),
    window_hours: int = 24,
) -> dict[str, Any]:
    """Real, org-scoped snapshot for the Intelligence Core visualization (Phase 2, 2026-09-11).

    Does not require admin — same rationale as `/models/catalog` and `/training-readiness`
    above (real org member access, not admin-gated).

    Every field is derived from live tables, never simulated:
    - Department breakdown comes from `intelligence_outcome_events.department`, the same
      column that already backs `OutcomeLearningService.get_department_outcome_summary`.
    - Pending-approval and active-agent-run counts are real org-level signals
      (`workflow_runs`, `memory_promotion_candidates`, `agent_swarm_runs`). Today's schema does
      not attribute these to a single department, so they are reported at the core/org level
      only rather than guessed into a department bucket.
    """
    window_hours = min(max(window_hours, 1), 168)
    client = get_supabase_client(settings)
    now = datetime.now(timezone.utc)

    outcome_service = get_outcome_learning_service(settings)
    recent_events = await outcome_service.fetch_recent_events(org_id, since_hours=window_hours)

    by_department: dict[str, dict[str, Any]] = {}
    for row in recent_events:
        dept_id = str(row.get("department") or "").strip().lower()
        if not dept_id:
            continue
        bucket = by_department.setdefault(
            dept_id,
            {"total": 0, "inflow": 0, "resolved": 0, "confidence_sum": 0.0, "confidence_count": 0},
        )
        bucket["total"] += 1
        event_name = row.get("outcome_event")
        if event_name in _CORE_INFLOW_EVENTS:
            bucket["inflow"] += 1
        if event_name in POSITIVE_EVENTS:
            bucket["resolved"] += 1
        confidence = row.get("confidence_score")
        if confidence is not None:
            try:
                bucket["confidence_sum"] += float(confidence)
                bucket["confidence_count"] += 1
            except (TypeError, ValueError):
                pass

    departments: list[dict[str, Any]] = []
    for dept_id, bucket in sorted(by_department.items()):
        confidence_avg = (
            round(bucket["confidence_sum"] / bucket["confidence_count"], 3)
            if bucket["confidence_count"]
            else None
        )
        if bucket["inflow"] > 0:
            visual_state = "flow-inward"
        elif bucket["resolved"] > 0:
            visual_state = "resolved"
        elif confidence_avg is not None and confidence_avg < 0.5:
            visual_state = "low-confidence"
        else:
            visual_state = "idle"
        departments.append(
            {
                "id": dept_id,
                "eventsInWindow": bucket["total"],
                "recentInflow": bucket["inflow"],
                "recentResolved": bucket["resolved"],
                "confidence": confidence_avg,
                "state": visual_state,
            }
        )

    pending_workflow_approvals = 0
    try:
        approvals_resp = (
            client.table("workflow_runs")
            .select("id", count="exact")
            .eq("org_id", org_id)
            .eq("run_type", RUN_TYPE_EXECUTE)
            .eq("status", RUN_STATUS_PENDING_APPROVAL)
            .eq("approval_status", RUN_STATUS_PENDING_APPROVAL)
            .execute()
        )
        pending_workflow_approvals = int(approvals_resp.count or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("core_state_workflow_approvals_skipped org_id=%s error=%s", org_id, exc)

    pending_memory_approvals = 0
    try:
        memory_result = get_memory_promotion_service(settings).list_candidates(
            org_id, status=MemoryPromotionStatus.PENDING_APPROVAL.value, limit=1
        )
        pending_memory_approvals = int(memory_result.get("total") or 0)
    except Exception as exc:  # noqa: BLE001
        logger.debug("core_state_memory_candidates_skipped org_id=%s error=%s", org_id, exc)

    active_agent_runs = 0
    try:
        swarm_runs = list_swarm_runs(client, org_id, limit=50)
        active_agent_runs = sum(
            1 for run in swarm_runs if run.get("status") in {SWARM_RUNNING, SWARM_AGGREGATING}
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("core_state_swarm_runs_skipped org_id=%s error=%s", org_id, exc)

    pending_approvals_total = pending_workflow_approvals + pending_memory_approvals
    if active_agent_runs > 0:
        core_visual_state = "trace"
    elif pending_approvals_total > 0:
        core_visual_state = "pending-approval"
    elif any(d["state"] == "flow-inward" for d in departments):
        core_visual_state = "flow-inward"
    elif recent_events:
        core_visual_state = "resolved" if any(d["state"] == "resolved" for d in departments) else "idle"
    else:
        core_visual_state = "idle"

    return {
        "generatedAt": now.isoformat(),
        "windowHours": window_hours,
        "core": {
            "state": core_visual_state,
            "activeAgentRuns": active_agent_runs,
            "pendingWorkflowApprovals": pending_workflow_approvals,
            "pendingMemoryApprovals": pending_memory_approvals,
            "pendingApprovalsTotal": pending_approvals_total,
        },
        "departments": departments,
        "note": (
            f"Department breakdown reflects intelligence_outcome_events in the last "
            f"{window_hours}h. Pending approvals and active agent runs are real org-level "
            "signals; current schema does not attribute them to a specific department."
        ),
    }
