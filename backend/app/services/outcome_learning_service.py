"""Unified outcome tracking across all Gravitre intelligence systems."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

MIN_OUTCOMES = 5

OUTCOME_EVENTS = frozenset(
    [
        "recommendation_created",
        "recommendation_approved",
        "recommendation_rejected",
        "prediction_generated",
        "prediction_validated",
        "prediction_missed",
        "workflow_executed",
        "workflow_failed",
        "connector_action_executed",
        "connector_action_failed",
        "business_metric_improved",
        "business_metric_declined",
        "user_feedback_positive",
        "user_feedback_negative",
        "approval_required",
        "approval_granted",
        "approval_denied",
        # Item 4 — CRM-labeled outcomes (stored primarily in crm_recommendation_outcomes;
        # also allowed here so learning ingest can mirror when wired).
        "crm_contacted",
        "crm_replied",
        "crm_booked",
        "crm_won",
        "crm_lost",
    ]
)

POSITIVE_EVENTS = frozenset(
    {
        "recommendation_approved",
        "prediction_validated",
        "workflow_executed",
        "connector_action_executed",
        "business_metric_improved",
        "user_feedback_positive",
        "approval_granted",
        "crm_won",
        "crm_booked",
        "crm_replied",
    }
)


class OutcomeLearningService:
    """
    Unified outcome tracking across all Gravitre intelligence systems. Extends v8's
    outcome_attribution_service and v7's response_evaluation_service — does not replace either.
    """

    TABLE = "intelligence_outcome_events"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _validate_event(self, outcome_event: str) -> None:
        if outcome_event not in OUTCOME_EVENTS:
            raise ValueError(f"Invalid outcome_event: {outcome_event}")

    def _fire_and_forget(self, coro: Any) -> None:
        asyncio.create_task(coro)

    async def _insert_event(self, payload: dict[str, Any]) -> None:
        try:
            self._client().table(self.TABLE).insert(payload).execute()
            self._mirror_clickhouse(payload)
            from app.services.learning_signal_aggregator import get_learning_signal_aggregator

            await get_learning_signal_aggregator(self.settings).ingest_outcome_event(payload)
        except Exception as exc:  # noqa: BLE001
            logger.debug("outcome_learning_insert_skipped error=%s", exc)

    def _mirror_clickhouse(self, row: dict[str, Any]) -> None:
        try:
            from app.services.clickhouse_service import get_clickhouse_service

            ch_row = {
                "org_id": str(row.get("org_id") or ""),
                "outcome_event": str(row.get("outcome_event") or ""),
                "entity_type": str(row.get("entity_type") or ""),
                "entity_id": str(row.get("entity_id") or ""),
                "model_name": str(row.get("model_name") or ""),
                "confidence_score": float(row.get("confidence_score") or 0),
                "created_at": datetime.now(timezone.utc).replace(tzinfo=None),
            }
            asyncio.create_task(
                get_clickhouse_service().insert_events("gravitre.intelligence_outcome_events", [ch_row])
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("outcome_learning_clickhouse_skipped error=%s", exc)

    async def record_recommendation_outcome(
        self,
        org_id: str,
        recommendation_id: str,
        outcome_event: str,
        *,
        department: str | None = None,
        task_type: str | None = None,
        model_name: str | None = None,
        confidence_score: float | None = None,
        before_value: float | None = None,
        after_value: float | None = None,
        measured_at: str | None = None,
        strategy_key: str | None = None,
        domain_context: dict[str, Any] | None = None,
        retrieval_effectiveness: dict[str, Any] | None = None,
    ) -> None:
        self._validate_event(outcome_event)
        metadata: dict[str, Any] = {}
        if strategy_key:
            metadata["strategy_key"] = strategy_key
        if domain_context:
            metadata["domain"] = {
                "industry": domain_context.get("industry_key") or domain_context.get("industry"),
                "department": domain_context.get("department_key") or domain_context.get("department"),
                "subdomain": domain_context.get("subdomain_key") or domain_context.get("subdomain"),
                "confidence": domain_context.get("confidence"),
                "profile_id": domain_context.get("profile_id"),
            }
        if retrieval_effectiveness:
            metadata["retrieval_effectiveness"] = retrieval_effectiveness
        payload = {
            "id": str(uuid4()),
            "org_id": org_id,
            "outcome_event": outcome_event,
            "entity_type": "recommendation",
            "entity_id": recommendation_id,
            "recommendation_id": recommendation_id,
            "department": department,
            "task_type": task_type,
            "model_name": model_name,
            "confidence_score": confidence_score,
            "before_value": before_value,
            "after_value": after_value,
            "measured_at": measured_at,
            "measurement_status": "recorded" if measured_at else "pending",
            "metadata": metadata,
            "created_at": self._now_iso(),
        }
        await self._insert_event(payload)

    def record_recommendation_outcome_async(self, **kwargs: Any) -> None:
        self._fire_and_forget(self.record_recommendation_outcome(**kwargs))

    async def record_crm_outcome(
        self,
        *,
        org_id: str,
        outcome_event: str,
        external_record_id: str,
        recommendation_id: str | None = None,
        connector_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Async CRM label write into intelligence_outcome_events (Phase 5.1)."""
        self._validate_event(outcome_event)
        meta = dict(metadata or {})
        if connector_type:
            meta.setdefault("connector_type", connector_type)
        entity_id = recommendation_id or external_record_id
        payload = {
            "id": str(uuid4()),
            "org_id": org_id,
            "outcome_event": outcome_event,
            "entity_type": "crm_deal" if not recommendation_id else "recommendation",
            "entity_id": entity_id,
            "recommendation_id": recommendation_id or external_record_id,
            "department": "sales",
            "task_type": "crm_outcome",
            "model_name": None,
            "confidence_score": None,
            "before_value": None,
            "after_value": None,
            "measured_at": self._now_iso(),
            "measurement_status": "recorded",
            "metadata": meta,
            "created_at": self._now_iso(),
        }
        await self._insert_event(payload)

    def record_crm_outcome_async(self, **kwargs: Any) -> None:
        self._fire_and_forget(self.record_crm_outcome(**kwargs))

    async def record_prediction_outcome(
        self,
        org_id: str,
        prediction_id: str,
        model_name: str,
        predicted_value: float,
        actual_value: float | None,
        outcome_event: str,
        measurement_available: bool = True,
    ) -> dict[str, Any]:
        self._validate_event(outcome_event)
        if not measurement_available:
            return {"measurement_status": "insufficient_data", "prediction_id": prediction_id}
        if actual_value is None:
            try:
                from app.temporal.starters import start_outcome_measurement_workflow

                await start_outcome_measurement_workflow(prediction_id)
            except Exception as exc:  # noqa: BLE001
                logger.debug("outcome_measurement_schedule_skipped id=%s error=%s", prediction_id, exc)
            return {
                "measurement_status": "pending_measurement",
                "prediction_id": prediction_id,
                "model_name": model_name,
            }
        accuracy = 1.0 - min(1.0, abs(float(predicted_value) - float(actual_value)) / max(abs(float(actual_value)), 1.0))
        payload = {
            "id": str(uuid4()),
            "org_id": org_id,
            "outcome_event": outcome_event,
            "entity_type": "prediction",
            "entity_id": prediction_id,
            "prediction_id": prediction_id,
            "model_name": model_name,
            "before_value": predicted_value,
            "after_value": actual_value,
            "measured_at": self._now_iso(),
            "measurement_status": "recorded",
            "metadata": {"accuracy": round(accuracy, 4)},
            "created_at": self._now_iso(),
        }
        await self._insert_event(payload)
        return {"measurement_status": "recorded", "accuracy": round(accuracy, 4)}

    async def record_workflow_outcome(
        self,
        org_id: str,
        workflow_id: str,
        workflow_run_id: str,
        outcome_event: str,
        error: str | None = None,
    ) -> None:
        self._validate_event(outcome_event)
        payload = {
            "id": str(uuid4()),
            "org_id": org_id,
            "outcome_event": outcome_event,
            "entity_type": "workflow",
            "entity_id": workflow_id,
            "workflow_id": workflow_id,
            "workflow_run_id": workflow_run_id,
            "metadata": {"error": error} if error else {},
            "created_at": self._now_iso(),
        }
        await self._insert_event(payload)

    async def record_agent_outcome(
        self,
        org_id: str,
        agent_id: str,
        task_description: str,
        outcome_event: str,
        execution_mode: str | None = None,
    ) -> None:
        self._validate_event(outcome_event)
        payload = {
            "id": str(uuid4()),
            "org_id": org_id,
            "outcome_event": outcome_event,
            "entity_type": "agent",
            "entity_id": agent_id,
            "agent_id": agent_id,
            "metadata": {"task_description": task_description, "execution_mode": execution_mode},
            "created_at": self._now_iso(),
        }
        await self._insert_event(payload)

    async def record_connector_action_outcome(
        self,
        org_id: str,
        connector_id: str,
        action_name: str,
        outcome_event: str,
        latency_ms: int | None = None,
    ) -> None:
        self._validate_event(outcome_event)
        payload = {
            "id": str(uuid4()),
            "org_id": org_id,
            "outcome_event": outcome_event,
            "entity_type": "connector",
            "entity_id": connector_id,
            "connector_id": connector_id,
            "metadata": {"action_name": action_name, "latency_ms": latency_ms},
            "created_at": self._now_iso(),
        }
        await self._insert_event(payload)

    async def _fetch_events(
        self,
        org_id: str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        since_days: int = 30,
    ) -> list[dict[str, Any]]:
        try:
            since = datetime.now(timezone.utc).replace(microsecond=0)
            q = (
                self._client()
                .table(self.TABLE)
                .select("*")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(500)
            )
            if entity_type:
                q = q.eq("entity_type", entity_type)
            if entity_id:
                q = q.eq("entity_id", entity_id)
            rows = q.execute().data or []
            return rows
        except Exception as exc:  # noqa: BLE001
            logger.debug("outcome_learning_fetch_skipped org_id=%s error=%s", org_id, exc)
            return []

    async def calculate_outcome_score(
        self,
        org_id: str,
        entity_type: str,
        entity_id: str,
        since_days: int = 30,
    ) -> dict[str, Any]:
        rows = await self._fetch_events(org_id, entity_type=entity_type, entity_id=entity_id, since_days=since_days)
        if len(rows) < MIN_OUTCOMES:
            return {
                "status": "insufficient_data",
                "min_required": MIN_OUTCOMES,
                "events_found": len(rows),
                "entity_type": entity_type,
                "entity_id": entity_id,
            }
        positive = sum(1 for row in rows if row.get("outcome_event") in POSITIVE_EVENTS)
        score = positive / len(rows) if rows else 0.0
        return {
            "status": "ok",
            "score": round(score, 4),
            "events_count": len(rows),
            "entity_type": entity_type,
            "entity_id": entity_id,
        }

    async def get_model_outcome_score(self, org_id: str, model_name: str) -> dict[str, Any]:
        rows = await self._fetch_events(org_id)
        model_rows = [r for r in rows if str(r.get("model_name") or "") == model_name]
        if len(model_rows) < MIN_OUTCOMES:
            return {"status": "insufficient_data", "min_required": MIN_OUTCOMES, "model_name": model_name}
        positive = sum(1 for row in model_rows if row.get("outcome_event") in POSITIVE_EVENTS)
        return {
            "status": "ok",
            "model_name": model_name,
            "score": round(positive / len(model_rows), 4),
            "events_count": len(model_rows),
        }

    async def get_agent_success_rate(self, org_id: str, agent_id: str) -> dict[str, Any]:
        return await self.calculate_outcome_score(org_id, "agent", agent_id)

    async def get_workflow_success_rate(self, org_id: str, workflow_id: str) -> dict[str, Any]:
        return await self.calculate_outcome_score(org_id, "workflow", workflow_id)

    async def get_department_outcome_summary(self, org_id: str, department: str) -> dict[str, Any]:
        rows = await self._fetch_events(org_id)
        dept_rows = [r for r in rows if str(r.get("department") or "").lower() == department.lower()]
        if len(dept_rows) < MIN_OUTCOMES:
            return {"status": "insufficient_data", "department": department, "min_required": MIN_OUTCOMES}
        positive = sum(1 for row in dept_rows if row.get("outcome_event") in POSITIVE_EVENTS)
        return {
            "status": "ok",
            "department": department,
            "score": round(positive / len(dept_rows), 4),
            "events_count": len(dept_rows),
        }

    async def get_training_signal_candidates(self, org_id: str) -> list[dict[str, Any]]:
        rows = await self._fetch_events(org_id)
        candidates: list[dict[str, Any]] = []
        for row in rows:
            if not row.get("measured_at"):
                continue
            before = row.get("before_value")
            after = row.get("after_value")
            if before is None and after is None and row.get("outcome_event") not in POSITIVE_EVENTS:
                continue
            candidates.append(
                {
                    "outcome_event": row.get("outcome_event"),
                    "model_name": row.get("model_name"),
                    "task_type": row.get("task_type"),
                    "department": row.get("department"),
                    "before_value": before,
                    "after_value": after,
                    "measured_at": row.get("measured_at"),
                }
            )
        return candidates

    async def load_admin_outcomes_summary(self, org_id: str, *, period_days: int = 7) -> dict[str, Any]:
        rows = await self._fetch_events(org_id, since_days=period_days)
        by_event: dict[str, int] = {}
        by_department: dict[str, int] = {}
        insufficient = 0
        for row in rows:
            event = str(row.get("outcome_event") or "unknown")
            by_event[event] = by_event.get(event, 0) + 1
            dept = str(row.get("department") or "unknown")
            by_department[dept] = by_department.get(dept, 0) + 1
            if row.get("measurement_status") == "insufficient_data":
                insufficient += 1
        total = len(rows) or 1
        return {
            "summary": {"total_events": len(rows), "period_days": period_days},
            "by_event_type": by_event,
            "by_department": by_department,
            "recent_events": rows[:20],
            "insufficient_data_rate": round(insufficient / total, 4),
            "period_days": period_days,
        }

    async def get_domain_optimization_metrics(self, org_id: str, *, period_days: int = 30) -> dict[str, Any]:
        summary = await self.load_admin_outcomes_summary(org_id, period_days=period_days)
        return {
            "total_events": summary.get("summary", {}).get("total_events", 0),
            "insufficient_data_rate": summary.get("insufficient_data_rate"),
            "by_event_type": summary.get("by_event_type") or {},
            "by_department": summary.get("by_department") or {},
            "period_days": period_days,
        }


_outcome_learning_service: OutcomeLearningService | None = None


def get_outcome_learning_service(settings: Settings | None = None) -> OutcomeLearningService:
    global _outcome_learning_service
    if _outcome_learning_service is None or settings is not None:
        _outcome_learning_service = OutcomeLearningService(settings)
    return _outcome_learning_service
