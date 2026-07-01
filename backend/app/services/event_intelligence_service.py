"""Fire-and-forget intelligence updates on significant connector write events."""
from __future__ import annotations

import asyncio
from typing import Any

from app.config import Settings, get_settings
from app.core.logging import get_logger
from app.workflows.repository import get_supabase_client

logger = get_logger(__name__)

WRITE_ACTION_SUFFIXES = (
    ".create",
    ".update",
    ".delete",
    ".enroll",
    ".add_contact",
)


class EventIntelligenceService:
    """
    Triggers intelligence updates on significant connector events.
    Called fire-and-forget from tool_service after confirmed write actions.
    Never blocks the connector response.
    """

    EVENT_HANDLERS: dict[tuple[str, str], str] = {
        ("hubspot", "deal.stage_changed"): "_handle_deal_stage_change",
        ("stripe", "subscription.updated"): "_handle_subscription_update",
        ("zendesk", "ticket.created"): "_handle_support_ticket_created",
    }

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _client(self) -> Any:
        return get_supabase_client(self.settings)

    @staticmethod
    def infer_event_type(connector: str, action: str, payload: dict[str, Any]) -> str | None:
        normalized = action.lower()
        if connector == "hubspot" and normalized.endswith("deals.update_stage"):
            return "deal.stage_changed"
        if connector == "stripe" and "subscription" in normalized and "update" in normalized:
            return "subscription.updated"
        if connector == "zendesk" and normalized.endswith("tickets.create"):
            return "ticket.created"
        if payload.get("event_type"):
            return str(payload["event_type"])
        return None

    @staticmethod
    def is_write_action(action: str) -> bool:
        lowered = action.lower()
        return any(lowered.endswith(suffix) for suffix in WRITE_ACTION_SUFFIXES)

    async def handle_connector_event(
        self,
        org_id: str,
        connector: str,
        event_type: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        handler_name = self.EVENT_HANDLERS.get((connector.lower(), event_type))
        if not handler_name:
            return
        handler = getattr(self, handler_name)
        asyncio.create_task(handler(org_id, entity_id, payload))

    def schedule_connector_event(
        self,
        org_id: str,
        connector: str,
        action: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        event_type = self.infer_event_type(connector, action, payload)
        if not event_type:
            return
        asyncio.create_task(
            self.handle_connector_event(org_id, connector, event_type, entity_id, payload)
        )

    async def _handle_deal_stage_change(
        self,
        org_id: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        logger.info(
            "event_intelligence_deal_stage org_id=%s deal_id=%s stage=%s",
            org_id,
            entity_id,
            payload.get("stage") or payload.get("dealstage"),
        )
        try:
            from app.services.optimization_suggestion_service import get_optimization_suggestion_service

            await get_optimization_suggestion_service(self.settings).detect_suggestions_for_org(org_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("event_intelligence_deal_stage_skipped error=%s", exc)

    async def _handle_subscription_update(
        self,
        org_id: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        logger.info(
            "event_intelligence_subscription org_id=%s subscription_id=%s",
            org_id,
            entity_id,
        )

    async def _handle_support_ticket_created(
        self,
        org_id: str,
        entity_id: str,
        payload: dict[str, Any],
    ) -> None:
        logger.info(
            "event_intelligence_support_ticket org_id=%s ticket_id=%s",
            org_id,
            entity_id,
        )
        try:
            from app.services.optimization_suggestion_service import get_optimization_suggestion_service

            service = get_optimization_suggestion_service(self.settings)
            await service.detect_suggestions_for_org(org_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("event_intelligence_ticket_suggestion_skipped error=%s", exc)


_event_intelligence_service: EventIntelligenceService | None = None


def get_event_intelligence_service(settings: Settings | None = None) -> EventIntelligenceService:
    global _event_intelligence_service
    if _event_intelligence_service is None or settings is not None:
        _event_intelligence_service = EventIntelligenceService(settings)
    return _event_intelligence_service
