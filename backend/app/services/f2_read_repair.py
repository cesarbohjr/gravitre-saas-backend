"""Phase F2 — bounded READ repair/retry/fallback from a blocked PreflightResult.

Does not change WRITE governance. Does not expand the F1 ActionSpec slice.
One repair attempt only — invalid provider invocation remains forbidden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.connectors.action_catalog.f1_read_slice import catalog_action_key, registry_action_key
from app.services.read_preflight import PreflightResult, preflight_read_action
from app.services.tool_types import ToolContext

_LISTING_INTENT = re.compile(r"(?i)\b(list|show|what'?s there|all (?:my )?deals|pipeline)\b")
_STRUCTURED_SEARCH = re.compile(
    r"(?i)\b(high[- ]value|over|greater than|amount|stage|won|lost|filter)\b"
)


@dataclass(frozen=True)
class ReadRepair:
    kind: str
    action: str
    args: dict[str, Any]
    preflight: PreflightResult | None
    reason: str


def _listing_without_criteria(message: str) -> bool:
    text = message or ""
    if _STRUCTURED_SEARCH.search(text):
        return False
    return bool(_LISTING_INTENT.search(text))


def repair_blocked_read(
    *,
    blocked: PreflightResult,
    ctx: ToolContext,
    invoke_action: str,
    args: dict[str, Any] | None,
    user_message: str,
    connected_integrations: list[str] | None,
) -> ReadRepair | None:
    """Return a single alternate READ, or None to keep the original block."""
    error = str(blocked.error_class or "")
    catalog = catalog_action_key(invoke_action)
    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}

    if error == "WRONG_SIBLING_ACTION" and catalog == "hubspot.deals.search" and _listing_without_criteria(
        user_message
    ):
        return ReadRepair(
            kind="reinvoke",
            action="hubspot.deals.list",
            args={"limit": int((args or {}).get("limit") or 10)},
            preflight=None,
            reason="sibling_list_fallback",
        )

    if (
        catalog == "google_analytics.reports.run"
        and error in {"AUTH_EXPIRED", "NOT_AUTHENTICATED", "NOT_CONFIGURED", "ACTION_UNAVAILABLE"}
        and "google_search_console" in connected
    ):
        fallback = preflight_read_action(
            context={
                "action_key": "google_search_console.searchAnalytics.query",
                "org_id": ctx.org_id,
                "client": ctx.client,
                "settings": ctx.settings,
                "proposed_args": dict(args or {}),
                "user_message": user_message,
                "environment_name": ctx.environment_name,
                "connected_integrations": list(connected),
                "turn_id": getattr(ctx, "conversation_id", None),
                "plan_id": getattr(ctx, "run_id", None),
                "step_id": getattr(ctx, "step_id", None),
            }
        )
        if fallback.ok:
            return ReadRepair(
                kind="reinvoke",
                action=registry_action_key(fallback.action_key or "google_search_console.searchAnalytics.query"),
                args=dict(fallback.compiled_parameters),
                preflight=fallback,
                reason="ga4_auth_fallback_gsc",
            )
    return None
