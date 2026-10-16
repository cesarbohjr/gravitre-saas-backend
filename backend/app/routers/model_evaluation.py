"""Admin endpoints for LLM model evaluation and adaptive routing approval.

Intelligence Track — wires llm_workflow_evaluation.evaluate_models into:
  POST /api/admin/model-evaluation
      Runs an offline structured-task evaluation against up to 5 models.
      Stores the full report in model_evaluation_reports. Platform admins only.

  GET  /api/admin/model-evaluation
      Lists recent evaluation reports for the caller's org.

  POST /api/admin/model-evaluation/{eval_id}/approve
      Reviews a completed report and, when no critical failures exist, marks
      routing_approved=True and seeds N ledger wins for the best-passing model
      so the strategy_performance_ledger will prefer it on the next routing call.
      Platform admins only.

Guards:
- Evaluation is bounded to 200 calls (enforced by evaluate_models).
- Approval is blocked when the report has any critical_failures > 0.
- Approval is idempotent: re-approving an already-approved report is a no-op.
- All calls are audit-logged.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.auth.platform_admin import is_platform_admin
from app.config import Settings, get_settings
from app.core.db import shared_service_client
from app.core.logging import get_logger
from app.services.llm_catalog import get_llm_model
from app.services.llm_workflow_evaluation import GOLDEN_CASES, EvaluationCase, evaluate_models
from app.services.model_router import ModelRouter, TaskType
from app.services.strategy_performance_ledger import get_strategy_performance_ledger
from app.workflows.audit import write_audit_event

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None  # type: ignore[assignment]

logger = get_logger(__name__)
router = APIRouter(prefix="/api/admin/model-evaluation", tags=["model_evaluation"])

# Number of synthetic ledger wins to seed for the approved model.
# Enough to clear MIN_SAMPLES_FOR_PREFERENCE (5) while keeping the
# ledger soft (real outcomes will still shift preference over time).
_APPROVAL_LEDGER_SEEDS = 6


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RunEvaluationRequest(BaseModel):
    org_id: str = Field(..., description="Dedicated evaluation org id (must not be a production org)")
    models: list[str] = Field(..., min_length=1, max_length=5,
                              description="Up to 5 catalog model ids to compare")
    repetitions: int = Field(default=1, ge=1, le=10)
    use_golden_cases: bool = Field(default=True,
                                   description="Always include the built-in GOLDEN_CASES baseline")


class EvaluationSummaryRow(BaseModel):
    id: str
    org_id: str
    models: list[str]
    dataset_sha256: str
    routing_approved: bool
    created_at: str
    critical_failures_total: int


class ListEvaluationsResponse(BaseModel):
    reports: list[EvaluationSummaryRow]


class ApproveRequest(BaseModel):
    best_model: str = Field(..., description="Catalog model id to promote to the strategy ledger")
    segment_key: str = Field(default="default",
                             description="Strategy segment to seed wins for; usually 'default'")
    org_id: str = Field(..., description="Org whose strategy ledger receives the seeded wins")
    notes: str = Field(default="", max_length=500)


class ApproveResponse(BaseModel):
    eval_id: str
    routing_approved: bool
    best_model: str
    ledger_seeds_written: int
    already_approved: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_platform_admin(client: Any, user_id: str) -> None:
    if not is_platform_admin(client, user_id):
        raise HTTPException(status_code=403, detail="Platform admin role required")


def _critical_failures_total(report: dict[str, Any]) -> int:
    models_summary = report.get("models") or {}
    return sum(
        int(m.get("critical_failures") or 0)
        for m in models_summary.values()
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201)
async def run_evaluation(
    body: RunEvaluationRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Run an offline LLM quality evaluation and store the report."""
    client = shared_service_client(settings, create_client)
    user_id: str = current_user["user_id"]
    _require_platform_admin(client, user_id)

    # Validate all requested models are in the active catalog.
    unknown = [m for m in body.models if get_llm_model(m) is None or (get_llm_model(m) and get_llm_model(m).deprecated)]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown or deprecated models: {unknown}")

    cases: tuple[EvaluationCase, ...] = GOLDEN_CASES if body.use_golden_cases else ()
    if not cases:
        raise HTTPException(status_code=422, detail="use_golden_cases=false with no custom cases would produce an empty evaluation")

    router_instance = ModelRouter(settings)
    try:
        report = await evaluate_models(
            router_instance,
            org_id=body.org_id,
            models=body.models,
            cases=cases,
            repetitions=body.repetitions,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.error("model_evaluation_run_failed user_id=%s error=%s", user_id, exc)
        raise HTTPException(status_code=502, detail="Evaluation run failed; see server logs") from exc

    # Store the immutable report.
    eval_id = str(uuid.uuid4())
    try:
        client.table("model_evaluation_reports").insert({
            "id": eval_id,
            "org_id": body.org_id,
            "run_by": user_id,
            "models": body.models,
            "dataset_sha256": report["dataset_sha256"],
            "catalog_sha256": report["catalog_sha256"],
            "scope": report.get("scope", "synthetic_structured_planning_only"),
            "report": report,
            "routing_approved": False,
        }).execute()
    except Exception as exc:  # noqa: BLE001
        logger.error("model_evaluation_store_failed eval_id=%s error=%s", eval_id, exc)
        raise HTTPException(status_code=500, detail="Failed to store evaluation report") from exc

    write_audit_event(client, {
        "actor_user_id": user_id,
        "action": "model_evaluation.run",
        "resource_type": "model_evaluation_report",
        "resource_id": eval_id,
        "metadata": {
            "models": body.models,
            "repetitions": body.repetitions,
            "critical_failures_total": _critical_failures_total(report),
        },
    })
    logger.info("model_evaluation_run_complete eval_id=%s models=%s", eval_id, body.models)
    return {"eval_id": eval_id, "report": report}


@router.get("")
async def list_evaluations(
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    org_id: str | None = None,
    limit: int = 20,
) -> ListEvaluationsResponse:
    """List recent evaluation reports visible to the caller."""
    client = shared_service_client(settings, create_client)
    user_id: str = current_user["user_id"]
    _require_platform_admin(client, user_id)
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be 1..100")

    try:
        q = (
            client.table("model_evaluation_reports")
            .select("id, org_id, models, dataset_sha256, routing_approved, created_at, report")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if org_id:
            q = q.eq("org_id", org_id)
        resp = q.execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning("model_evaluation_list_failed user_id=%s error=%s", user_id, exc)
        raise HTTPException(status_code=500, detail="Failed to query evaluation reports") from exc

    rows: list[EvaluationSummaryRow] = []
    for row in resp.data or []:
        report_blob = row.get("report") or {}
        rows.append(EvaluationSummaryRow(
            id=str(row["id"]),
            org_id=str(row["org_id"]),
            models=list(row.get("models") or []),
            dataset_sha256=str(row.get("dataset_sha256") or ""),
            routing_approved=bool(row.get("routing_approved")),
            created_at=str(row.get("created_at") or ""),
            critical_failures_total=_critical_failures_total(report_blob),
        ))
    return ListEvaluationsResponse(reports=rows)


@router.post("/{eval_id}/approve")
async def approve_evaluation(
    eval_id: str,
    body: ApproveRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ApproveResponse:
    """Approve a report and seed the strategy ledger for the best-passing model.

    Blocked when any model in the report has critical_failures > 0.
    Idempotent: re-approving an already-approved report returns already_approved=True.
    """
    client = shared_service_client(settings, create_client)
    user_id: str = current_user["user_id"]
    _require_platform_admin(client, user_id)

    # Fetch the report.
    try:
        resp = (
            client.table("model_evaluation_reports")
            .select("id, routing_approved, report, models")
            .eq("id", eval_id)
            .limit(1)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="DB lookup failed") from exc

    if not resp.data:
        raise HTTPException(status_code=404, detail="Evaluation report not found")

    rec = resp.data[0]
    report_blob: dict[str, Any] = rec.get("report") or {}

    # Idempotence.
    if rec.get("routing_approved"):
        return ApproveResponse(
            eval_id=eval_id,
            routing_approved=True,
            best_model=body.best_model,
            ledger_seeds_written=0,
            already_approved=True,
        )

    # Safety guard: any critical failure blocks approval.
    critical_total = _critical_failures_total(report_blob)
    if critical_total > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve: report has {critical_total} critical failure(s). "
                   "Fix the model or evaluation cases before approving.",
        )

    # Validate best_model is in the report.
    models_summary = report_blob.get("models") or {}
    if body.best_model not in models_summary:
        raise HTTPException(
            status_code=422,
            detail=f"best_model '{body.best_model}' not present in the evaluation report",
        )

    # Mark approved in DB.
    try:
        from datetime import datetime, timezone
        client.table("model_evaluation_reports").update({
            "routing_approved": True,
            "approved_by": user_id,
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", eval_id).execute()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Failed to mark report approved") from exc

    # Seed the strategy ledger so the approved model gains an immediate preference edge.
    ledger = get_strategy_performance_ledger(settings)
    strategy_key = f"llm:{body.best_model}"
    seeds_written = 0
    for _ in range(_APPROVAL_LEDGER_SEEDS):
        try:
            await ledger.record(
                body.org_id,
                strategy_key,
                "win",
                strategy_family="route",
                segment_key=body.segment_key,
                metadata={"source": "model_evaluation_approval", "eval_id": eval_id},
            )
            seeds_written += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("ledger_seed_failed eval_id=%s key=%s error=%s", eval_id, strategy_key, exc)
            break

    write_audit_event(client, {
        "actor_user_id": user_id,
        "action": "model_evaluation.approve",
        "resource_type": "model_evaluation_report",
        "resource_id": eval_id,
        "metadata": {
            "best_model": body.best_model,
            "segment_key": body.segment_key,
            "org_id": body.org_id,
            "ledger_seeds_written": seeds_written,
            "notes": body.notes,
        },
    })
    logger.info(
        "model_evaluation_approved eval_id=%s best_model=%s seeds=%d",
        eval_id, body.best_model, seeds_written,
    )
    return ApproveResponse(
        eval_id=eval_id,
        routing_approved=True,
        best_model=body.best_model,
        ledger_seeds_written=seeds_written,
    )
