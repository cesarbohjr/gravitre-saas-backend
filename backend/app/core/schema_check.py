"""Best-effort startup check that columns the code depends on actually exist.

Migrations and the live database can drift (a migration skipped, an
``IF NOT EXISTS`` that kept an older table shape). This check runs once in the
background after startup, issues one cheap PostgREST ``select <col> limit 0``
per column, and logs a structured warning naming any column that is missing.

It never blocks or fails startup, and it is skipped under tests.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# table -> columns the backend reads/writes and would break without.
SCHEMA_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "custom_instructions": ("kind", "department"),
    "goals": ("category",),
    "agent_memories": ("is_current",),
    "org_metric_definitions": ("definition",),
    # Phase 2A outbox (migration 20261012024141); logs until the migration is applied.
    "domain_event_outbox": ("event_type", "status", "lease_owner", "delivered_handlers"),
    # Phase 2B purge receipts (migration 20261012024200).
    "source_purge_receipts": ("connector_id", "disconnected_at", "dry_run", "counts"),
}

DISABLE_ENV = "GRAVITRE_STARTUP_SCHEMA_CHECK"


def _running_under_tests() -> bool:
    return "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _disabled_by_env() -> bool:
    return (os.environ.get(DISABLE_ENV) or "").strip().lower() in {"0", "false", "off", "no"}


def check_schema_columns(
    client: Any,
    dependencies: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Probe each column with ``select(col).limit(0)``; collect the ones that fail."""
    deps = dependencies or SCHEMA_DEPENDENCIES
    missing: list[dict[str, str]] = []
    checked = 0
    for table, columns in deps.items():
        for column in columns:
            checked += 1
            try:
                client.table(table).select(column).limit(0).execute()
            except Exception as exc:  # noqa: BLE001 - any failure means "not usable"
                missing.append({"table": table, "column": column, "error": str(exc)[:300]})
    return {"ok": not missing, "checked": checked, "missing": missing}


async def run_startup_schema_check(*, force: bool = False, client: Any | None = None) -> dict[str, Any] | None:
    """Run the check off the event loop and log the result. Never raises."""
    if not force and (_running_under_tests() or _disabled_by_env()):
        return None
    try:
        if client is None:
            from app.config import get_settings
            from app.workflows.repository import get_supabase_client

            client = get_supabase_client(get_settings())
        result = await asyncio.to_thread(check_schema_columns, client)
    except Exception as exc:  # noqa: BLE001 - best effort, startup must not fail
        logger.warning("startup_schema_check_skipped error=%s", exc)
        return None
    if result["ok"]:
        logger.info("startup_schema_check_ok checked=%s", result["checked"])
    else:
        logger.warning(
            "startup_schema_check_missing_columns checked=%s missing=%s",
            result["checked"],
            [f"{m['table']}.{m['column']}" for m in result["missing"]],
            extra={"schema_check": result},
        )
    return result


def start_startup_schema_check() -> asyncio.Task | None:
    """Schedule the check as a background task (None when skipped)."""
    if _running_under_tests() or _disabled_by_env():
        return None
    return asyncio.create_task(run_startup_schema_check())
