"""Fire-and-forget outcome tracking after intelligence responses."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class OutcomeTracker:
    """
    Records post-response outcomes for v7/v8 learning loops.
    Never blocks the user response.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def track(
        self,
        org_id: str,
        agent_id: str | None,
        message_id: str | None,
        action_taken: dict[str, Any] | None,
        response: dict[str, Any],
        classification: dict[str, Any],
    ) -> None:
        asyncio.create_task(
            self._track_async(
                org_id,
                agent_id,
                message_id,
                action_taken,
                response,
                classification,
            )
        )

    async def _track_async(
        self,
        org_id: str,
        agent_id: str | None,
        message_id: str | None,
        action_taken: dict[str, Any] | None,
        response: dict[str, Any],
        classification: dict[str, Any],
    ) -> None:
        try:
            if action_taken and action_taken.get("metric_before") is not None:
                from app.services.outcome_attribution_service import get_outcome_attribution_service

                await get_outcome_attribution_service(self.settings).record_action_baseline(
                    org_id=org_id,
                    agent_id=agent_id,
                    workflow_run_id=action_taken.get("workflow_run_id"),
                    action_type=str(action_taken.get("type") or action_taken.get("action_type") or "unknown"),
                    target_entity_type=str(action_taken.get("entity_type") or "unknown"),
                    target_entity_id=str(action_taken.get("entity_id") or "unknown"),
                    metric_name=str(action_taken.get("metric_name") or "custom_metric"),
                    metric_value_before=action_taken.get("metric_before"),
                )
            if message_id:
                from app.services.response_evaluation_service import consolidate_recent

                await consolidate_recent(self.settings, org_id, since_days=1)
            from app.services.learning_feedback_loop import get_learning_feedback_loop

            await get_learning_feedback_loop(self.settings).process_feedback(
                org_id,
                "response_quality" if message_id else "action_outcome",
                {
                    "message_id": message_id,
                    "response": response,
                    "classification": classification,
                    "action_taken": action_taken,
                },
            )
            asyncio.create_task(self._write_clickhouse(org_id, classification, message_id))
        except Exception as exc:  # noqa: BLE001
            logger.debug("outcome_tracker_skipped org_id=%s error=%s", org_id, exc)

    async def _write_clickhouse(
        self,
        org_id: str,
        classification: dict[str, Any],
        message_id: str | None,
    ) -> None:
        try:
            from app.services.clickhouse_service import get_clickhouse_service

            await get_clickhouse_service().insert_events(
                "gravitre.pipeline_events",
                [
                    {
                        "org_id": org_id,
                        "stage_name": "outcome_tracked",
                        "intent": classification.get("intent"),
                        "message_id": message_id,
                    }
                ],
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("outcome_tracker_clickhouse_skipped org_id=%s error=%s", org_id, exc)


_outcome_tracker: OutcomeTracker | None = None


def get_outcome_tracker(settings: Settings | None = None) -> OutcomeTracker:
    global _outcome_tracker
    if _outcome_tracker is None or settings is not None:
        _outcome_tracker = OutcomeTracker(settings)
    return _outcome_tracker
