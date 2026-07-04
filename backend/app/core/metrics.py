"""Structured business event logging for future alerting."""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def log_business_event(
    event_type: str,
    org_id: str | None = None,
    **kwargs: Any,
) -> None:
    """Emit a structured business event (Railway log alerts, observability pipelines)."""
    logger.info(
        "business_event:%s",
        event_type,
        extra={
            "event_type": event_type,
            "org_id": org_id or "",
            **kwargs,
        },
    )
