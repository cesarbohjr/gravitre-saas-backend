"""Outcome-informed recommendation ranking and feedback loop."""
from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.services.outcome_learning_service import get_outcome_learning_service

logger = get_logger(__name__)

MIN_QUALITY_THRESHOLD = 0.35


class RecommendationQualityEngine:
    """Closes the loop between recommendation generation and historical outcomes."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._outcomes = get_outcome_learning_service(self.settings)

    async def rank_recommendations(
        self,
        recommendations: list[dict[str, Any]],
        *,
        org_id: str,
        department: str | None = None,
    ) -> list[dict[str, Any]]:
        dept_summary = (
            await self._outcomes.get_department_outcome_summary(org_id, department)
            if department
            else {"status": "insufficient_data"}
        )
        dept_score = float(dept_summary.get("score") or 0.0) if dept_summary.get("status") == "ok" else 0.5

        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in recommendations:
            base = float(row.get("confidence") or row.get("score") or 0.5)
            rec_id = str(row.get("id") or row.get("recommendation_id") or "")
            historical = await self._historical_success_rate(org_id, rec_id, row)
            quality = round(min(1.0, 0.55 * base + 0.25 * historical + 0.2 * dept_score), 4)
            enriched = dict(row)
            enriched["quality_score"] = quality
            enriched["historical_success_rate"] = historical
            enriched["department_outcome_score"] = dept_score if dept_summary.get("status") == "ok" else None
            if quality >= MIN_QUALITY_THRESHOLD:
                ranked.append((quality, enriched))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in ranked]

    async def filter_actionable(
        self,
        recommendations: list[dict[str, Any]],
        *,
        org_id: str,
        department: str | None = None,
    ) -> list[dict[str, Any]]:
        ranked = await self.rank_recommendations(recommendations, org_id=org_id, department=department)
        return ranked[:5]

    async def record_recommendation_created(
        self,
        *,
        org_id: str,
        recommendation_id: str,
        department: str | None = None,
        task_type: str | None = None,
        confidence_score: float | None = None,
        strategy_key: str | None = None,
    ) -> None:
        await self._outcomes.record_recommendation_outcome(
            org_id,
            recommendation_id,
            "recommendation_created",
            department=department,
            task_type=task_type,
            confidence_score=confidence_score,
            strategy_key=strategy_key,
        )

    async def record_recommendation_feedback(
        self,
        *,
        org_id: str,
        recommendation_id: str,
        accepted: bool,
        department: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        _ = metadata
        await self._outcomes.record_recommendation_outcome(
            org_id,
            recommendation_id,
            "recommendation_approved" if accepted else "recommendation_rejected",
            department=department,
        )

    def stable_recommendation_id(self, org_id: str, action: str, source: str) -> str:
        digest = hashlib.sha256(f"{org_id}:{action}:{source}".encode()).hexdigest()[:24]
        return f"rec_{digest}"

    async def enrich_decision_recommendations(
        self,
        org_id: str,
        recommendations: list[dict[str, Any]],
        *,
        department: str | None = None,
    ) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for row in recommendations:
            action = str(row.get("action") or row.get("title") or "")
            rec_id = str(row.get("id") or self.stable_recommendation_id(org_id, action, "decision"))
            payload = dict(row)
            payload["id"] = rec_id
            enriched.append(payload)
            await self.record_recommendation_created(
                org_id=org_id,
                recommendation_id=rec_id,
                department=department,
                confidence_score=float(row.get("confidence") or 0.55),
            )
        return await self.rank_recommendations(enriched, org_id=org_id, department=department)

    async def _historical_success_rate(
        self,
        org_id: str,
        recommendation_id: str,
        row: dict[str, Any],
    ) -> float:
        if recommendation_id:
            result = await self._outcomes.calculate_outcome_score(
                org_id,
                "recommendation",
                recommendation_id,
                since_days=90,
            )
            if result.get("status") == "ok":
                return float(result.get("score") or 0.5)
        source = str(row.get("source") or row.get("suggestion_type") or row.get("suggestionType") or "")
        if source:
            result = await self._outcomes.calculate_outcome_score(org_id, "recommendation_type", source, since_days=90)
            if result.get("status") == "ok":
                return float(result.get("score") or 0.5)
        return 0.5


_engine: RecommendationQualityEngine | None = None


def get_recommendation_quality_engine(settings: Settings | None = None) -> RecommendationQualityEngine:
    global _engine
    if _engine is None or settings is not None:
        _engine = RecommendationQualityEngine(settings)
    return _engine
