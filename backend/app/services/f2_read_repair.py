"""Phase F2 — classed READ repair budget from a blocked PreflightResult.

Does not change WRITE governance. Invalid provider invocation remains forbidden.
Sibling / source-switch targets that are F1 keys must HMAC-preflight before invoke.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.connectors.action_catalog.f1_read_slice import catalog_action_key, is_f1_read_action, registry_action_key
from app.services.read_preflight import PreflightResult, preflight_read_action
from app.services.tool_types import ToolContext

_LISTING_INTENT = re.compile(r"(?i)\b(list|show|what'?s there|all (?:my )?deals|pipeline)\b")
_STRUCTURED_SEARCH = re.compile(
    r"(?i)\b(high[- ]value|over|greater than|amount|stage|won|lost|filter)\b"
)

# transport 2, argument 2, resource rediscover 1, sibling 1, source switch 1, replan 1
REPAIR_BUDGET_BY_CLASS: dict[str, int] = {
    "transport": 2,
    "argument": 2,
    "resource_rediscover": 1,
    "sibling": 1,
    "source_switch": 1,
    "replan": 1,
}

_ERROR_CLASS_TO_BUDGET: dict[str, str] = {
    "WRONG_SIBLING_ACTION": "sibling",
    "AUTH_EXPIRED": "source_switch",
    "NOT_AUTHENTICATED": "source_switch",
    "NOT_CONFIGURED": "source_switch",
    "ACTION_UNAVAILABLE": "source_switch",
    "AUTH_UNAVAILABLE": "source_switch",
    "PARAMETER_UNRESOLVED": "argument",
    "SCHEMA_INVALID": "argument",
    "PROVIDER_CONSTRAINT_INVALID": "argument",
    "RESOURCE_UNRESOLVED": "resource_rediscover",
    "RESOURCE_AMBIGUOUS": "resource_rediscover",
    "RATE_LIMITED": "transport",
    "TIMEOUT": "transport",
    "TRANSPORT_ERROR": "transport",
}


@dataclass
class RepairBudget:
    remaining: dict[str, int] = field(default_factory=lambda: dict(REPAIR_BUDGET_BY_CLASS))
    traces: list[dict[str, Any]] = field(default_factory=list)
    _fingerprints: set[str] = field(default_factory=set)

    @classmethod
    def fresh(cls) -> RepairBudget:
        return cls()

    def classify(self, error_class: str | None) -> str | None:
        return _ERROR_CLASS_TO_BUDGET.get(str(error_class or ""))

    def consume(self, repair_class: str, *, fingerprint: str, reason: str) -> bool:
        if fingerprint in self._fingerprints:
            self.traces.append(
                {
                    "repair_class": repair_class,
                    "fingerprint": fingerprint,
                    "accepted": False,
                    "reason": "same_malformed_args",
                }
            )
            return False
        left = int(self.remaining.get(repair_class, 0) or 0)
        if left <= 0:
            self.traces.append(
                {
                    "repair_class": repair_class,
                    "fingerprint": fingerprint,
                    "accepted": False,
                    "reason": "budget_exhausted",
                    "remaining": dict(self.remaining),
                }
            )
            return False
        self.remaining[repair_class] = left - 1
        self._fingerprints.add(fingerprint)
        self.traces.append(
            {
                "repair_class": repair_class,
                "fingerprint": fingerprint,
                "accepted": True,
                "reason": reason,
                "remaining": dict(self.remaining),
            }
        )
        return True


@dataclass(frozen=True)
class ReadRepair:
    kind: str
    action: str
    args: dict[str, Any]
    preflight: PreflightResult | None
    reason: str
    repair_class: str = ""
    budget_remaining: dict[str, int] = field(default_factory=dict)


def _listing_without_criteria(message: str) -> bool:
    text = message or ""
    if _STRUCTURED_SEARCH.search(text):
        return False
    return bool(_LISTING_INTENT.search(text))


def _preflight_context(
    *,
    action_key: str,
    ctx: ToolContext,
    args: dict[str, Any] | None,
    user_message: str,
    connected: set[str],
) -> dict[str, Any]:
    return {
        "action_key": action_key,
        "org_id": ctx.org_id,
        "client": ctx.client,
        "settings": ctx.settings,
        "proposed_args": dict(args or {}),
        "user_message": user_message,
        "environment_name": ctx.environment_name,
        "connected_integrations": list(connected),
        "turn_id": getattr(ctx, "turn_id", None) or getattr(ctx, "conversation_id", None),
        "plan_id": getattr(ctx, "plan_id", None),
        "step_id": getattr(ctx, "step_id", None),
    }


def _hmac_ready_repair(
    *,
    action: str,
    ctx: ToolContext,
    args: dict[str, Any] | None,
    user_message: str,
    connected: set[str],
    reason: str,
    repair_class: str,
    budget: RepairBudget,
) -> ReadRepair | None:
    fallback = preflight_read_action(
        context=_preflight_context(
            action_key=action,
            ctx=ctx,
            args=args,
            user_message=user_message,
            connected=connected,
        )
    )
    if not fallback.ok:
        return None
    if is_f1_read_action(action) and not fallback.proof_digest:
        return None
    return ReadRepair(
        kind="reinvoke",
        action=registry_action_key(fallback.action_key or action),
        args=dict(fallback.compiled_parameters),
        preflight=fallback,
        reason=reason,
        repair_class=repair_class,
        budget_remaining=dict(budget.remaining),
    )


def repair_blocked_read(
    *,
    blocked: PreflightResult,
    ctx: ToolContext,
    invoke_action: str,
    args: dict[str, Any] | None,
    user_message: str,
    connected_integrations: list[str] | None,
    budget: RepairBudget | None = None,
) -> ReadRepair | None:
    """Return one alternate READ within class budget, or None to keep the original block."""
    error = str(blocked.error_class or "")
    catalog = catalog_action_key(invoke_action)
    connected = {str(v).strip().lower() for v in (connected_integrations or []) if str(v).strip()}
    purse = budget if budget is not None else RepairBudget.fresh()
    repair_class = purse.classify(error)
    if repair_class is None:
        return None

    fingerprint = f"{repair_class}:{catalog}:{error}"

    if error == "WRONG_SIBLING_ACTION" and catalog == "hubspot.deals.search" and _listing_without_criteria(
        user_message
    ):
        if not purse.consume(repair_class, fingerprint=fingerprint, reason="sibling_list_fallback"):
            return None
        repaired = _hmac_ready_repair(
            action="hubspot.deals.list",
            ctx=ctx,
            args={"limit": int((args or {}).get("limit") or 10)},
            user_message=user_message,
            connected=connected,
            reason="sibling_list_fallback",
            repair_class=repair_class,
            budget=purse,
        )
        return repaired

    if (
        catalog == "google_analytics.reports.run"
        and error in {"AUTH_EXPIRED", "NOT_AUTHENTICATED", "NOT_CONFIGURED", "ACTION_UNAVAILABLE"}
        and "google_search_console" in connected
    ):
        if not purse.consume(repair_class, fingerprint=fingerprint, reason="ga4_auth_fallback_gsc"):
            return None
        return _hmac_ready_repair(
            action="google_search_console.searchAnalytics.query",
            ctx=ctx,
            args=args,
            user_message=user_message,
            connected=connected,
            reason="ga4_auth_fallback_gsc",
            repair_class=repair_class,
            budget=purse,
        )
    return None
