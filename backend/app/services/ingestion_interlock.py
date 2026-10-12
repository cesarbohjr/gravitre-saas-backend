"""Customer ingestion stays inert until source lifecycle is enforced.

Customer data may only be turned into derived data (entities, observations,
behaviour signals, pilot indexing) once removing a source also removes what
was derived from it. Until every lifecycle prerequisite below is switched on,
the ingestion flags do nothing, whatever their own value, and startup logs
which prerequisite is missing.

Two kinds of ingestion are covered, and treated differently on purpose:

* **New ingestion** (``INGESTION_FLAGS``): the entity writer, customer
  observations, behaviour signals and the in-process indexing pilot. Held
  until the lifecycle prerequisites hold, and then only for connectors whose
  provider has a revoke call wired (``provider_lifecycle_supported``).
* **Existing ingestion**: the knowledge syncs customers already rely on
  (Notion, Confluence, HubSpot, Zendesk, Workday: scheduled, manual and
  webhook) and the standalone ``app.rag.worker``. These keep running exactly
  as before unless the owner sets ``EXISTING_INGESTION_REQUIRES_LIFECYCLE=true``
  (default false). ``ingestion_interlock_report`` and the startup log say
  which state applies, so a deployment where they are still ungated is visible.

Limitations (read before relying on this as a privacy control):

* The prerequisites are configuration flags, not proof of enforcement. Nothing
  here checks that the domain event relay task is alive, that the
  ``source.disconnected`` handler is registered, or that the purge and claim
  migrations are applied.
* Revoke on disconnect is a no-op (``not_supported``) for Notion, Microsoft 365,
  Zendesk, Atlassian (Confluence, Jira), Intercom, Workday and every other vendor
  outside ``provider_revoke.SUPPORTED_VENDORS``. New ingestion is therefore
  refused for those providers even when every flag is on.
* The M1 purge (``purge_connector_derived_data``) does not delete
  ``entity_observations`` or ``entity_behavior_signals`` directly. They go only
  by cascade with their ``org_business_entities`` row, so an account also bound
  to another vendor keeps the disconnected vendor's observations and signals.
* Read paths (account cards, health, feeds) are not gated here.
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

# Owner switch for the pre-existing ingestion paths; default keeps them running.
EXISTING_INGESTION_FLAG = "existing_ingestion_requires_lifecycle"

# Vendors that run the pre-existing knowledge syncs (knowledge_sync_service + Workday route).
KNOWLEDGE_SYNC_VENDORS: tuple[str, ...] = ("notion", "confluence", "hubspot", "zendesk", "workday")

LIMITATIONS: tuple[str, ...] = (
    (
        "prerequisites are configuration flags only; relay liveness, handler registration "
        "and applied migrations are not checked"
    ),
    (
        "revoke on disconnect is not wired for notion, microsoft365, zendesk, atlassian "
        "(confluence, jira), intercom, workday; new ingestion is refused for them"
    ),
    (
        "the M1 purge does not delete entity_observations or entity_behavior_signals of "
        "accounts still bound to another vendor"
    ),
)


class IngestionHeldError(RuntimeError):
    """Ingestion was refused by the lifecycle interlock. Routes answer 503."""


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


def provider_lifecycle_supported(vendor: str | None) -> bool:
    """True only for vendors whose grant we can revoke at the provider on disconnect.

    Unknown or empty vendors fail closed.
    """
    try:
        from app.connectors.provider_revoke import SUPPORTED_VENDORS, canonical_vendor

        v = canonical_vendor(vendor)
    except Exception as exc:  # noqa: BLE001
        logger.warning("provider_lifecycle_lookup_failed vendor=%s error=%s", vendor, type(exc).__name__)
        return False
    return bool(v) and v in SUPPORTED_VENDORS


def ingestion_allowed_for_provider(settings: Any, flag: str, vendor: str | None) -> bool:
    """A new-ingestion ``flag`` is effective for data from ``vendor``."""
    return ingestion_flag_on(settings, flag) and provider_lifecycle_supported(vendor)


def existing_ingestion_gated(settings: Any) -> bool:
    return getattr(settings, EXISTING_INGESTION_FLAG, False) is True


def existing_ingestion_hold_reason(settings: Any, vendor: str | None = None) -> str | None:
    """Why a pre-existing ingestion path must not run, or None to run as before.

    With ``EXISTING_INGESTION_REQUIRES_LIFECYCLE`` off (the default) this is always
    None: existing knowledge syncs and the standalone worker are not changed.
    """
    if not existing_ingestion_gated(settings):
        return None
    missing = missing_lifecycle_prerequisites(settings)
    if missing:
        return "lifecycle_prerequisites_missing:" + ",".join(missing)
    if vendor is not None and not provider_lifecycle_supported(vendor):
        return f"provider_revoke_not_supported:{str(vendor).strip().lower() or 'unknown'}"
    return None


def ensure_existing_ingestion_allowed(settings: Any, vendor: str | None = None) -> None:
    reason = existing_ingestion_hold_reason(settings, vendor)
    if reason:
        logger.warning("existing_ingestion_held vendor=%s reason=%s", vendor, reason)
        raise IngestionHeldError(f"Ingestion is held until source lifecycle is enforced ({reason})")


def ingestion_interlock_report(settings: Any) -> dict[str, Any]:
    """Readiness report: what is held, what still runs ungated, and why."""
    missing = missing_lifecycle_prerequisites(settings)
    gated = existing_ingestion_gated(settings)
    sync_vendors: dict[str, str] = {}
    for vendor in KNOWLEDGE_SYNC_VENDORS:
        if not gated:
            sync_vendors[vendor] = "running_ungated"
        else:
            reason = existing_ingestion_hold_reason(settings, vendor)
            sync_vendors[vendor] = f"held:{reason}" if reason else "allowed"
    return {
        "lifecycle_ready": not missing,
        "prerequisites": {
            name: {
                "required": want,
                "actual": getattr(settings, name, None),
                "ok": getattr(settings, name, not want) is want,
            }
            for name, want in LIFECYCLE_PREREQUISITES
        },
        "missing": missing,
        "new_ingestion": {
            flag: {
                "requested": getattr(settings, flag, False) is True,
                "effective": ingestion_flag_on(settings, flag),
            }
            for flag in INGESTION_FLAGS
        },
        "existing_ingestion": {
            "requires_lifecycle": gated,
            "knowledge_sync": sync_vendors,
            "standalone_worker": "running_ungated"
            if not gated
            else ("held" if missing else "allowed"),
        },
        "providers_without_revoke": sorted(
            v for v in KNOWLEDGE_SYNC_VENDORS if not provider_lifecycle_supported(v)
        ),
        "limitations": list(LIMITATIONS),
    }


def log_ingestion_interlock(settings: Any) -> list[str]:
    """Log once at startup which ingestion is held or ungated. Returns held new-ingestion flags."""
    requested = [f for f in INGESTION_FLAGS if getattr(settings, f, False) is True]
    missing = missing_lifecycle_prerequisites(settings)
    if not existing_ingestion_gated(settings) and missing:
        # Existing knowledge syncs keep queueing customer text while lifecycle is not enforced.
        logger.warning(
            "customer_ingestion_interlock existing_ingestion=ungated "
            "knowledge_sync=%s missing=%s set=%s=true to hold",
            ",".join(KNOWLEDGE_SYNC_VENDORS),
            ",".join(missing),
            EXISTING_INGESTION_FLAG.upper(),
        )
    if requested and missing:
        logger.warning(
            "customer_ingestion_interlock held=%s missing=%s",
            ",".join(f.upper() for f in requested),
            ",".join(missing),
        )
        return requested
    return []
