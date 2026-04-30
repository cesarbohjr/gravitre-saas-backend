from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.config import get_settings
from app.core.logging import get_logger
from app.services.model_router import TaskType, get_model_router
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)


class RecommendationType(StrEnum):
    REORDER_STEPS = "reorder_steps"
    ADD_VALIDATION = "add_validation"
    PARALLELIZE = "parallelize"
    ADD_RETRY = "add_retry"
    REMOVE_BOTTLENECK = "remove_bottleneck"
    SIMPLIFY = "simplify"


class Recommendation(BaseModel):
    id: str
    type: RecommendationType
    title: str
    issue: str
    suggested_change: str
    estimated_impact: str
    confidence: float = Field(ge=0.0, le=1.0)
    risk: str


class OptimizationService:
    def __init__(self):
        self.settings = get_settings()
        self.model_router = get_model_router()

    async def analyze_workflow(self, org_id: str, workflow_id: str, days: int = 30) -> list[Recommendation]:
        client = get_supabase_client(self.settings)
        runs_resp = (
            client.table("workflow_runs")
            .select("id,status,error,last_error,duration_ms,created_at")
            .eq("org_id", org_id)
            .eq("workflow_id", workflow_id)
            .limit(500)
            .execute()
        )
        runs = runs_resp.data or []
        if not runs:
            return []

        failed = [r for r in runs if str(r.get("status")) in {"failed", "error"}]
        avg_duration = sum(float(r.get("duration_ms") or 0.0) for r in runs) / max(1, len(runs))
        recs: list[Recommendation] = []
        if failed and (len(failed) / len(runs)) > 0.2:
            recs.append(
                Recommendation(
                    id=f"{workflow_id}:retry",
                    type=RecommendationType.ADD_RETRY,
                    title="Increase resiliency with retries",
                    issue="Failure rate exceeds 20% in observed runs.",
                    suggested_change="Add retry logic with bounded backoff on unstable connector/action steps.",
                    estimated_impact="Reduce failed runs by 10-30%.",
                    confidence=0.84,
                    risk="low",
                )
            )
        if avg_duration > 300000:
            recs.append(
                Recommendation(
                    id=f"{workflow_id}:parallel",
                    type=RecommendationType.PARALLELIZE,
                    title="Parallelize independent steps",
                    issue="Average run duration is above 5 minutes.",
                    suggested_change="Run non-dependent enrichment and notification steps concurrently.",
                    estimated_impact="Reduce latency by 15-40%.",
                    confidence=0.78,
                    risk="medium",
                )
            )

        prompt = (
            "Generate optimization recommendations for this workflow execution profile.\n"
            f"Days window: {days}\n"
            f"Run count: {len(runs)}\n"
            f"Failure count: {len(failed)}\n"
            f"Average duration ms: {avg_duration:.2f}\n"
            "Return concise bullet-style guidance."
        )
        try:
            ai = await self.model_router.complete(
                task_type=TaskType.OPTIMIZATION_ANALYSIS,
                prompt=prompt,
                org_id=org_id,
            )
            if ai.content and not recs:
                recs.append(
                    Recommendation(
                        id=f"{workflow_id}:simplify",
                        type=RecommendationType.SIMPLIFY,
                        title="Simplify workflow pathing",
                        issue="Workflow contains avoidable complexity.",
                        suggested_change=ai.content[:220],
                        estimated_impact="Lower operational overhead and faster triage.",
                        confidence=0.6,
                        risk="medium",
                    )
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("optimization AI suggestion skipped: %s", str(exc))

        self._persist_recommendations(org_id, workflow_id, recs)
        return recs

    def _persist_recommendations(self, org_id: str, workflow_id: str, recs: list[Recommendation]) -> None:
        if not recs:
            return
        client = get_supabase_client(self.settings)
        rows = [
            {
                "org_id": org_id,
                "workflow_id": workflow_id,
                "recommendation_type": rec.type.value,
                "title": rec.title,
                "issue": rec.issue,
                "suggested_change": rec.suggested_change,
                "estimated_impact": rec.estimated_impact,
                "confidence": rec.confidence,
                "risk": rec.risk,
            }
            for rec in recs
        ]
        try:
            client.table("optimization_recommendations").insert(rows).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("optimization recommendations insert failed: %s", str(exc))


_optimization_service_singleton: OptimizationService | None = None


def get_optimization_service() -> OptimizationService:
    global _optimization_service_singleton
    if _optimization_service_singleton is None:
        _optimization_service_singleton = OptimizationService()
    return _optimization_service_singleton
