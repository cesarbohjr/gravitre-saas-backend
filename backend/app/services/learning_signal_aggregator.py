"""Normalize feedback and outcome events into weighted learning signals."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

SIGNAL_WEIGHTS: dict[str, float] = {
    "explicit_helpful": 1.0,
    "explicit_not_helpful": 1.0,
    "user_correction": 0.9,
    "approval_granted": 0.85,
    "approval_denied": 0.85,
    "recommendation_approved": 0.8,
    "recommendation_rejected": 0.8,
    "workflow_executed": 0.6,
    "workflow_failed": 0.7,
    "workflow_abandoned": 0.5,
    "confidence_mismatch": 0.55,
    "user_feedback_positive": 0.75,
    "user_feedback_negative": 0.75,
}

OUTCOME_EVENT_SIGNAL_MAP: dict[str, tuple[str, str]] = {
    "recommendation_approved": ("recommendation_approved", "positive"),
    "recommendation_rejected": ("recommendation_rejected", "negative"),
    "approval_granted": ("approval_granted", "positive"),
    "approval_denied": ("approval_denied", "negative"),
    "user_feedback_positive": ("user_feedback_positive", "positive"),
    "user_feedback_negative": ("user_feedback_negative", "negative"),
    "workflow_executed": ("workflow_executed", "positive"),
    "workflow_failed": ("workflow_failed", "negative"),
    "prediction_validated": ("explicit_helpful", "positive"),
    "prediction_missed": ("explicit_not_helpful", "negative"),
}


class LearningSignalAggregator:
    TABLE = "intelligence_learning_signals"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    async def ingest(
        self,
        org_id: str,
        signal_type: str,
        polarity: str,
        *,
        weight: float | None = None,
        department: str | None = None,
        surface: str | None = None,
        strategy_key: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        confidence_delta: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if polarity not in {"positive", "negative", "neutral"}:
            polarity = "neutral"
        row = {
            "id": str(uuid4()),
            "org_id": org_id,
            "signal_type": signal_type,
            "polarity": polarity,
            "weight": float(weight if weight is not None else SIGNAL_WEIGHTS.get(signal_type, 0.5)),
            "department": department,
            "surface": surface,
            "strategy_key": strategy_key,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "confidence_delta": confidence_delta,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            self._client().table(self.TABLE).insert(row).execute()
            if strategy_key and polarity in {"positive", "negative"}:
                from app.services.strategy_performance_ledger import get_strategy_performance_ledger

                await get_strategy_performance_ledger(self.settings).record_from_signal(
                    org_id,
                    strategy_key,
                    polarity,
                    segment_key=str(department or "default"),
                    metadata=metadata,
                )
                from app.services.org_learning_profile_service import get_org_learning_profile_service

                delta = 0.05 if polarity == "positive" else -0.05
                await get_org_learning_profile_service(self.settings).update_segment_weight(
                    org_id,
                    str(department or "default"),
                    strategy_key=strategy_key,
                    weight_delta=delta,
                )
        except Exception as exc:  # noqa: BLE001
            logger.debug("learning_signal_insert_skipped org=%s type=%s error=%s", org_id, signal_type, exc)

    async def ingest_outcome_event(self, payload: dict[str, Any]) -> None:
        event = str(payload.get("outcome_event") or "")
        mapped = OUTCOME_EVENT_SIGNAL_MAP.get(event)
        if not mapped:
            return
        signal_type, polarity = mapped
        meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        strategy_key = meta.get("strategy_key") or payload.get("strategy_key")
        await self.ingest(
            org_id=str(payload.get("org_id") or ""),
            signal_type=signal_type,
            polarity=polarity,
            department=payload.get("department"),
            surface=meta.get("surface"),
            strategy_key=str(strategy_key) if strategy_key else None,
            entity_type=payload.get("entity_type"),
            entity_id=str(payload.get("entity_id") or payload.get("recommendation_id") or ""),
            confidence_delta=None,
            metadata={"outcome_event": event, **meta},
        )

    async def ingest_feedback(
        self,
        org_id: str,
        feedback_type: str,
        feedback_data: dict[str, Any],
    ) -> None:
        if feedback_type == "response_quality":
            helpful = feedback_data.get("helpful")
            strategy_key = feedback_data.get("strategy_key")
            surface = feedback_data.get("surface")
            department = feedback_data.get("segment_key")
            if helpful is True:
                await self.ingest(
                    org_id,
                    "explicit_helpful",
                    "positive",
                    strategy_key=strategy_key,
                    surface=surface,
                    department=department,
                    metadata=feedback_data,
                )
            elif helpful is False:
                await self.ingest(
                    org_id,
                    "explicit_not_helpful",
                    "negative",
                    strategy_key=strategy_key,
                    surface=surface,
                    department=department,
                    metadata=feedback_data,
                )
        elif feedback_type == "user_correction":
            await self.ingest(org_id, "user_correction", "negative", metadata=feedback_data)
        elif feedback_type == "approval_decision":
            granted = feedback_data.get("granted") is True or feedback_data.get("decision") == "approved"
            await self.ingest(
                org_id,
                "approval_granted" if granted else "approval_denied",
                "positive" if granted else "negative",
                metadata=feedback_data,
            )
        elif feedback_type == "action_outcome":
            success = feedback_data.get("success") is True
            await self.ingest(
                org_id,
                "workflow_executed" if success else "workflow_failed",
                "positive" if success else "negative",
                metadata=feedback_data,
            )

    async def load_summary(self, org_id: str, *, since_days: int = 30) -> dict[str, Any]:
        since = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
        try:
            rows = (
                self._client()
                .table(self.TABLE)
                .select("signal_type, polarity, weight, strategy_key")
                .eq("org_id", org_id)
                .gte("created_at", since)
                .order("created_at", desc=True)
                .limit(5000)
                .execute()
                .data
                or []
            )
        except Exception:  # noqa: BLE001
            rows = []
        positive = sum(float(r.get("weight") or 0) for r in rows if r.get("polarity") == "positive")
        negative = sum(float(r.get("weight") or 0) for r in rows if r.get("polarity") == "negative")
        total = positive + negative
        by_type: dict[str, int] = {}
        for row in rows:
            key = str(row.get("signal_type") or "unknown")
            by_type[key] = by_type.get(key, 0) + 1
        return {
            "signal_count": len(rows),
            "positive_weight": round(positive, 4),
            "negative_weight": round(negative, 4),
            "positive_ratio": round(positive / total, 4) if total else None,
            "by_type": by_type,
            "since_days": since_days,
        }


_aggregator: LearningSignalAggregator | None = None


def get_learning_signal_aggregator(settings: Settings | None = None) -> LearningSignalAggregator:
    global _aggregator
    if _aggregator is None or settings is not None:
        _aggregator = LearningSignalAggregator(settings)
    return _aggregator
