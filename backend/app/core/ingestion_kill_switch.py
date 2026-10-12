"""DISABLE_INGESTION kill switch: one check for every path that writes ingested data.

``Settings.disable_ingestion`` (env ``DISABLE_INGESTION``, default false) is the
emergency stop for customer-data ingestion. Paths that run in the background
(scheduled syncs, the entity writer, observation and signal handlers) call
``ingestion_disabled`` and skip; request paths call ``ensure_ingestion_enabled``,
whose ``IngestionDisabledError`` routers answer with 503.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

INGESTION_DISABLED_DETAIL = "Ingestion is disabled"


class IngestionDisabledError(RuntimeError):
    """DISABLE_INGESTION is on; nothing was written."""


def ingestion_disabled(settings: Any) -> bool:
    """True only when DISABLE_INGESTION is explicitly true."""
    return getattr(settings, "disable_ingestion", False) is True


def ensure_ingestion_enabled(settings: Any, path: str) -> None:
    """Raise ``IngestionDisabledError`` when the kill switch is on. ``path`` is for logs."""
    if ingestion_disabled(settings):
        logger.warning("ingestion_disabled_refused path=%s", path)
        raise IngestionDisabledError(INGESTION_DISABLED_DETAIL)
