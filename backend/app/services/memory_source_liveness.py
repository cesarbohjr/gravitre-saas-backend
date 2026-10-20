"""Read-time source liveness for derived context (memories, observations, signals).

The disconnect purge (``purge_connector_memories``) removes rows learned from a
connector, but it runs only when the domain-event relay is on and outside dry run.
Until it has run, and in the window between a disconnect and the purge, the rows
are still in the database. This module keeps them out of what Chat and Voice read:

* ``drop_memories_from_revoked_sources``: agent memories whose
  ``source_connector_id`` names a connector that is deleted, revoked, disconnected
  or gone are dropped from recall results. Untagged (legacy) memories are kept:
  they are classified and proposed for handling, never retired automatically.
* ``drop_observations_from_revoked_sources``: the same for customer observations;
  behaviour signals of an account are dropped when every observation read for it
  came from a revoked connector (signals carry no source of their own).
* ``invalidate_org_derived_context``: on a disconnect, bump the org's context epoch
  (part of the retrieval, instant-answer and source-summary cache keys, and checked
  by the connector read-result cache) and clear the in-process caches that hold
  connector-derived context for the org.

Everything here is a no-op with no database or cache access unless
MEMORY_SOURCE_LINEAGE_ENABLED is on. When it is on, a failed liveness read fails
closed: memories are dropped, tagged observations and all signals are dropped.
"""
from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.services.memory_contamination_guard import lineage_required

logger = get_logger(__name__)

# Same set the context engine's account inputs treat as dead (PR #393).
DEAD_CONNECTOR_STATUSES = frozenset({"revoked", "disconnected", "deleted", "inactive", "disabled"})

EPOCH_NAMESPACE = "context_epoch"
# Bumped whenever a knowledge source is deleted or a connector disconnected,
# independent of MEMORY_SOURCE_LINEAGE_ENABLED: retrieval caches key on it so
# removed documents stop being served from cache at once.
RETRIEVAL_EPOCH_NAMESPACE = "org_retrieval_epoch"
# Longer than the longest cache that keys on the epoch (instant answers, 1 hour).
EPOCH_TTL_SECONDS = 86400 * 2


def liveness_enabled(settings: Any = None) -> bool:
    return lineage_required(settings)


def _is_live(row: dict[str, Any] | None, org_id: str) -> bool:
    if not isinstance(row, dict):
        return False
    if str(row.get("org_id") or "") != str(org_id):
        return False
    if row.get("deleted_at"):
        return False
    return str(row.get("status") or "").strip().lower() not in DEAD_CONNECTOR_STATUSES


def live_connector_ids(client: Any, org_id: str, connector_ids: set[str] | list[str]) -> set[str]:
    """The subset of ``connector_ids`` that are live connectors of ``org_id``.

    A connector that is missing, belongs to another org, is soft-deleted or has a
    dead status is not live. Raises on read failure (callers fail closed).
    """
    ids = sorted({str(c).lower() for c in connector_ids if c})
    if not ids:
        return set()
    rows = (
        client.table("connectors")
        .select("id, org_id, status, deleted_at")
        .eq("org_id", org_id)
        .in_("id", ids)
        .execute()
        .data
        or []
    )
    return {str(r.get("id")).lower() for r in rows if _is_live(r, org_id)}


def _row_id(row: dict[str, Any]) -> str:
    return str(row.get("id") or row.get("memory_id") or "")


def drop_memories_from_revoked_sources(
    client: Any,
    org_id: str,
    rows: list[dict[str, Any]],
    *,
    settings: Any = None,
    surface: str = "",
) -> list[dict[str, Any]]:
    """Recall rows minus memories learned from a connector that is no longer live.

    Rows that already carry ``source_connector_id`` are judged on it; the lineage of
    the others is read by id (one query), then the connectors (one query). Rows
    whose lineage cannot be read, or that have no id, are dropped when the read
    fails (fail closed). Untagged memories are kept.
    """
    if not rows or not liveness_enabled(settings):
        return rows
    try:
        lineage: dict[str, str | None] = {}
        unknown: list[str] = []
        for row in rows:
            rid = _row_id(row)
            if "source_connector_id" in row:
                lineage[rid] = (str(row.get("source_connector_id") or "").lower() or None)
            elif rid:
                unknown.append(rid)
        if unknown:
            found = (
                client.table("agent_memories")
                .select("id, source_connector_id")
                .eq("org_id", org_id)
                .in_("id", sorted(set(unknown)))
                .execute()
                .data
                or []
            )
            for r in found:
                lineage[str(r.get("id"))] = (str(r.get("source_connector_id") or "").lower() or None)
        tagged = {c for c in lineage.values() if c}
        live = live_connector_ids(client, org_id, tagged) if tagged else set()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "memory_source_liveness_failed_closed org_id=%s surface=%s dropped=%s error=%s",
            org_id,
            surface,
            len(rows),
            str(exc)[:200],
        )
        return []
    kept: list[dict[str, Any]] = []
    dropped = 0
    for row in rows:
        rid = _row_id(row)
        if rid not in lineage:
            # Not found by id (deleted meanwhile, or no id at all): do not show it.
            dropped += 1
            continue
        connector = lineage[rid]
        if connector and connector not in live:
            dropped += 1
            continue
        kept.append(row)
    if dropped:
        logger.info(
            "memory_source_revoked_excluded org_id=%s surface=%s excluded=%s",
            org_id,
            surface,
            dropped,
        )
    return kept


def observation_columns(base: str, settings: Any = None) -> str:
    """``base`` plus ``source_connector_id`` when lineage is on (the column arrives
    with 20261012070000; flag-off reads stay exactly as they were)."""
    if liveness_enabled(settings) and "source_connector_id" not in base:
        return f"{base}, source_connector_id"
    return base


def drop_observations_from_revoked_sources(
    client: Any,
    org_id: str,
    observations: list[dict[str, Any]],
    signals: list[dict[str, Any]] | None = None,
    *,
    settings: Any = None,
    entity_id: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Observations minus those from a revoked connector, and the signals that remain.

    Signals are aggregates without a source. Those of an account are dropped when
    every observation read for it was tagged with a revoked connector (nothing it
    could have been built from is still live). ``entity_id`` names the account when
    the rows have no ``entity_id`` column (single-account reads).
    """
    signals = list(signals or [])
    if not liveness_enabled(settings):
        return observations, signals
    tagged = {str(o.get("source_connector_id")).lower() for o in observations if o.get("source_connector_id")}
    try:
        live = live_connector_ids(client, org_id, tagged) if tagged else set()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "observation_source_liveness_failed_closed org_id=%s error=%s", org_id, str(exc)[:200]
        )
        return [o for o in observations if not o.get("source_connector_id")], []

    def _entity(row: dict[str, Any]) -> str:
        return str(row.get("entity_id") or entity_id or "")

    kept: list[dict[str, Any]] = []
    revoked_entities: set[str] = set()
    surviving_entities: set[str] = set()
    for o in observations:
        connector = str(o.get("source_connector_id") or "").lower()
        if connector and connector not in live:
            revoked_entities.add(_entity(o))
            continue
        surviving_entities.add(_entity(o))
        kept.append(o)
    dead_only = revoked_entities - surviving_entities
    kept_signals = [s for s in signals if _entity(s) not in dead_only]
    excluded = len(observations) - len(kept)
    if excluded or len(kept_signals) != len(signals):
        logger.info(
            "observation_source_revoked_excluded org_id=%s observations=%s signals=%s",
            org_id,
            excluded,
            len(signals) - len(kept_signals),
        )
    return kept, kept_signals


# ---------------------------------------------------------------------------
# Cache invalidation on revoke
# ---------------------------------------------------------------------------


def org_context_epoch(org_id: str | None, settings: Any = None) -> str:
    """The org's current context epoch ("" when lineage is off or never bumped).

    Cache keys that include it stop matching once a source of the org is revoked.
    Shared across replicas through Redis when configured, else per process.
    """
    if not org_id or not liveness_enabled(settings):
        return ""
    try:
        from app.services.cache_service import get_cache_service

        value = get_cache_service().get_sync(EPOCH_NAMESPACE, str(org_id))
    except Exception:  # noqa: BLE001
        return ""
    return str(value or "")


def org_retrieval_epoch(org_id: str | None) -> str:
    """The org's retrieval epoch ("" until a source was deleted or disconnected).

    Always on. Shared across replicas through Redis when configured, else per
    process (then another replica can serve its cached retrieval until its TTL).
    """
    if not org_id:
        return ""
    try:
        from app.services.cache_service import get_cache_service

        value = get_cache_service().get_sync(RETRIEVAL_EPOCH_NAMESPACE, str(org_id))
    except Exception:  # noqa: BLE001
        return ""
    return str(value or "")


def epoch_parts(org_id: str | None, settings: Any = None) -> tuple[str, ...]:
    """Cache key suffix: empty when there is no epoch, so keys are unchanged."""
    parts: list[str] = []
    epoch = org_context_epoch(org_id, settings)
    if epoch:
        parts.append(f"epoch:{epoch}")
    retrieval = org_retrieval_epoch(org_id)
    if retrieval:
        parts.append(f"repoch:{retrieval}")
    return tuple(parts)


def cached_before_epoch(org_id: str | None, cached_at: float, settings: Any = None) -> bool:
    """True when an entry cached at ``cached_at`` (epoch seconds) predates a revoke."""
    epoch = org_context_epoch(org_id, settings)
    if not epoch:
        return False
    try:
        return float(cached_at) < float(epoch)
    except (TypeError, ValueError):
        return True


def invalidate_org_retrieval_cache(org_id: str | None, *, reason: str = "") -> bool:
    """Make cached retrieval for the org miss from now on (always on, never raises).

    Called when a knowledge source is deleted or a connector is disconnected. The
    documents themselves are deactivated in the same database transaction (see
    migration 20261013030000); this covers results cached before that.
    """
    if not org_id:
        return False
    try:
        from app.services.cache_service import get_cache_service

        get_cache_service().set_sync(
            RETRIEVAL_EPOCH_NAMESPACE, f"{time.time():.6f}", EPOCH_TTL_SECONDS, str(org_id)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("retrieval_epoch_bump_failed org_id=%s error=%s", org_id, str(exc)[:200])
        return False
    logger.info("org_retrieval_cache_invalidated org_id=%s reason=%s", org_id, reason)
    return True


def invalidate_org_derived_context(org_id: str | None, *, settings: Any = None, reason: str = "") -> bool:
    """Make every cache holding the org's connector-derived context miss from now on.

    Bumps the org's context epoch, then clears the in-process caches (connector read
    results, connected-integration snapshot, account names, org context and
    intelligence projection). Never raises. Returns False (and does nothing) when
    lineage is off.
    """
    if not org_id or not liveness_enabled(settings):
        return False
    org_id = str(org_id)
    try:
        from app.services.cache_service import get_cache_service

        get_cache_service().set_sync(EPOCH_NAMESPACE, f"{time.time():.6f}", EPOCH_TTL_SECONDS, org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("context_epoch_bump_failed org_id=%s error=%s", org_id, str(exc)[:200])
    _clear_in_process(org_id)
    logger.info("org_derived_context_invalidated org_id=%s reason=%s", org_id, reason)
    return True


def _clear_in_process(org_id: str) -> None:
    steps = (
        ("read_action_result_cache", "invalidate_org_read_results"),
        ("connector_snapshot_cache", "invalidate_org_connected"),
        ("entity_context_card", "invalidate_org_names"),
    )
    import importlib

    for module_name, fn_name in steps:
        try:
            module = importlib.import_module(f"app.services.{module_name}")
            getattr(module, fn_name)(org_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("derived_cache_clear_failed cache=%s org_id=%s error=%s", module_name, org_id, exc)
    try:
        from app.services.org_context_service import get_org_context_service

        get_org_context_service().invalidate_org(org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("derived_cache_clear_failed cache=org_context org_id=%s error=%s", org_id, exc)
    try:
        from app.services import intelligence_projection_service as ips

        if ips._service is not None:
            ips._service.invalidate(org_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("derived_cache_clear_failed cache=intelligence_projection org_id=%s error=%s", org_id, exc)
