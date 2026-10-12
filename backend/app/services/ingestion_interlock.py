"""Customer ingestion stays inert until source lifecycle is enforced.

Customer data may only be turned into derived data (entities, observations,
behaviour signals, pilot indexing) once removing a source also removes what
was derived from it. Until every lifecycle prerequisite below is switched on,
the ingestion flags do nothing, whatever their own value, and startup logs
which prerequisite is missing.

Read paths (account cards, health, feeds) are not gated here: with ingestion
inert they have nothing new to read.
"""
from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# (setting, value it must have)
LIFECYCLE_PREREQUISITES: tuple[tuple[str, bool], ...] = (
    ("domain_event_relay_enabled", True),
    ("source_deletion_propagation_enabled", True),
    ("connector_provider_revoke_on_disconnect", True),
    ("source_purge_dry_run", False),
)

INGESTION_FLAGS: tuple[str, ...] = (
    "entity_writer_enabled",
    "entity_observations_enabled",
    "entity_behavior_signals_enabled",
    "rag_worker_pilot_enabled",
)


def missing_lifecycle_prerequisites(settings: Any) -> list[str]:
    return [
        f"{name.upper()}={'true' if want else 'false'}"
        for name, want in LIFECYCLE_PREREQUISITES
        if getattr(settings, name, not want) is not want
    ]


def ingestion_flag_on(settings: Any, flag: str) -> bool:
    """``flag`` is on and the lifecycle prerequisites hold."""
    if getattr(settings, flag, False) is not True:
        return False
    return not missing_lifecycle_prerequisites(settings)


def log_ingestion_interlock(settings: Any) -> list[str]:
    """Log once at startup which ingestion flags are held back. Returns them."""
    requested = [f for f in INGESTION_FLAGS if getattr(settings, f, False) is True]
    missing = missing_lifecycle_prerequisites(settings)
    if requested and missing:
        logger.warning(
            "customer_ingestion_interlock held=%s missing=%s",
            ",".join(f.upper() for f in requested),
            ",".join(missing),
        )
        return requested
    return []
