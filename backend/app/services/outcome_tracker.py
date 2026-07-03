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
            from app.services.intelligence_outcome_coordinator import get_intelligence_outcome_coordinator

            await get_intelligence_outcome_coordinator(self.settings).record_response(
                org_id,
                agent_id=agent_id,
                message_id=message_id,
                action_taken=action_taken,
                response=response,
                classification=classification,
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
