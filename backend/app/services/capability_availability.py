"""Provider availability for capabilities, and runtime fallback across alternatives.

A capability (``prospect.discovery``, ``crm.deal.create`` …) binds to several
vendor actions. When a provider refuses work for a reason that will not clear
on retry (plan limit, expired auth, missing scope, rate limit, outage), the
refusal is recorded in ``connector_action_availability`` and the next
connected alternative is tried. Planning reads the same table, so a blocked
provider is replanned around instead of being retried every run.

Nothing here is department specific: every pack, Play, objective plan and chat
tool call that names a capability goes through it.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

TABLE = "connector_action_availability"
UNAVAILABLE_STATES = frozenset({"plan_limit", "auth_expired", "permission_denied", "rate_limited", "unhealthy"})

# How long a recorded refusal blocks planning before the provider is tried again.
_TTL = {
    "plan_limit": timedelta(hours=24),
    "auth_expired": timedelta(hours=6),
    "permission_denied": timedelta(hours=24),
    "rate_limited": timedelta(hours=1),
    "unhealthy": timedelta(minutes=15),
}

_PLAN_LIMIT_HINTS = (
    "plan limit", "upgrade your plan", "not available on your plan", "insufficient credits",
    "out of credits", "credit limit", "quota exceeded", "payment required", "402", "subscription",
)
_AUTH_HINTS = ("401", "unauthorized", "token expired", "invalid_grant", "reauthor", "re-authorize", "expired token")
_PERMISSION_HINTS = ("403", "forbidden", "missing scope", "insufficient scope", "not permitted by provider")
_RATE_HINTS = ("429", "rate limit", "too many requests")
_HEALTH_HINTS = ("502", "503", "504", "service unavailable", "bad gateway", "timed out", "timeout")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        value = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def vendor_of(action: str) -> str:
    return str(action or "").split(".", 1)[0].strip().lower()


@dataclass(frozen=True)
class Block:
    vendor: str
    action: str
    state: str
    reason: str | None
    expires_at: str | None


def load_blocks(client: Any, org_id: str, *, now: datetime | None = None) -> list[Block]:
    """Active provider refusals for an org (expired rows and 'available' are ignored)."""
    if client is None or not org_id:
        return []
    now = now or _now()
    try:
        rows = client.table(TABLE).select("vendor, action, state, reason, expires_at").eq("org_id", org_id).limit(500).execute().data or []
    except Exception as exc:  # noqa: BLE001 - table absent in older environments
        logger.debug("capability_availability_load_failed org_id=%s err=%s", org_id, exc)
        return []
    out = []
    for row in rows:
        state = str(row.get("state") or "")
        if state not in UNAVAILABLE_STATES:
            continue
        expires = _parse(row.get("expires_at"))
        if expires is not None and expires <= now:
            continue
        out.append(
            Block(
                vendor=str(row.get("vendor") or "").lower(),
                action=str(row.get("action") or "*"),
                state=state,
                reason=row.get("reason"),
                expires_at=row.get("expires_at"),
            )
        )
    return out


def blocked_reason(blocks: list[Block], action: str) -> Block | None:
    vendor = vendor_of(action)
    for block in blocks:
        if block.vendor == vendor and block.action in {"*", action}:
            return block
    return None


def record_unavailable(
    client: Any,
    org_id: str,
    *,
    action: str,
    state: str,
    reason: str | None = None,
    whole_vendor: bool | None = None,
    now: datetime | None = None,
) -> None:
    """Record that a provider refused work. Auth and plan problems block the whole vendor."""
    if client is None or not org_id or state not in UNAVAILABLE_STATES:
        return
    now = now or _now()
    vendor = vendor_of(action)
    # Auth and outages affect every action of a vendor. A plan limit is an
    # entitlement on one action (an Apollo plan can allow enrichment but not
    # people search), so it blocks only the refused action.
    scope_all = whole_vendor if whole_vendor is not None else state in {"auth_expired", "unhealthy"}
    key_action = "*" if scope_all else action
    payload = {
        "state": state,
        "reason": (reason or "")[:500] or None,
        "observed_at": now.isoformat(),
        "expires_at": (now + _TTL[state]).isoformat(),
    }
    try:
        updated = (
            client.table(TABLE).update(payload).eq("org_id", org_id).eq("vendor", vendor).eq("action", key_action).execute().data
            or []
        )
        if not updated:
            client.table(TABLE).insert({"org_id": org_id, "vendor": vendor, "action": key_action, **payload}).execute()
    except Exception as exc:  # noqa: BLE001 - availability is advisory; never fail the caller
        logger.warning("capability_availability_record_failed org_id=%s vendor=%s err=%s", org_id, vendor, exc)


def classify_failure(error: Any) -> str | None:
    """Map a provider failure to an availability state, or None when retrying elsewhere is unsafe.

    An uncertain write outcome is never a fallback trigger: the first provider
    may have applied it.
    """
    code = str(getattr(error, "code", None) or getattr(error, "error_code", None) or "").lower()
    message = str(getattr(error, "error_message", None) or (str(error) if isinstance(error, Exception) else "") or "").lower()
    if code == "outcome_uncertain":
        return None
    if code in {"auth_expired", "connector_not_connected"}:
        return "auth_expired"
    if code == "missing_scope":
        return "permission_denied"
    if code == "rate_limited":
        return "rate_limited"
    if code == "plan_limit" or any(h in message for h in _PLAN_LIMIT_HINTS):
        return "plan_limit"
    if any(h in message for h in _AUTH_HINTS):
        return "auth_expired"
    if any(h in message for h in _RATE_HINTS):
        return "rate_limited"
    if any(h in message for h in _PERMISSION_HINTS):
        return "permission_denied"
    if any(h in message for h in _HEALTH_HINTS):
        return "unhealthy"
    return None


# --------------------------------------------------------------------------- built-in providers

WEB_RESEARCH_ACTION = "gravitre.web.research"
_QUERY_SKIP = ("id", "_id", "token", "limit", "page", "per_page", "offset", "connector")


def _binds_web_research(capability_id: str) -> bool:
    from app.capability_ontology.registry import get_capability

    definition = get_capability(capability_id)
    return bool(definition) and definition.kind == "read" and any(
        b.action_key == WEB_RESEARCH_ACTION for b in definition.bindings
    )


def web_research_available(settings: Any) -> bool:
    try:
        from app.services.web_research import is_web_research_provider_configured

        return bool(settings) and is_web_research_provider_configured(settings)
    except Exception:  # noqa: BLE001
        return False


def _research_query(capability_id: str, params: dict[str, Any]) -> str:
    from app.capability_ontology.registry import get_capability

    parts: list[str] = []
    for key, value in params.items():
        if key.startswith("_") or any(key.lower().endswith(s) for s in _QUERY_SKIP):
            continue
        values = value if isinstance(value, list) else [value]
        for item in values:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
    definition = get_capability(capability_id)
    label = definition.label if definition else capability_id
    return " ".join(dict.fromkeys(parts))[:400] or label


def _run_coro(coro: Any) -> Any:
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def run_web_research(ctx: Any, capability_id: str, params: dict[str, Any]) -> Any:
    """Gravitre's built-in provider: public web research for read capabilities (no connector needed)."""
    from app.services.tool_types import NormalizedResult
    from app.services.web_research import search_web

    query = _research_query(capability_id, params)
    payload = _run_coro(
        search_web(
            query,
            settings=getattr(ctx, "settings", None),
            max_results=int(params.get("limit") or params.get("per_page") or 5),
            org_id=getattr(ctx, "org_id", None),
            client=getattr(ctx, "client", None),
        )
    ) or {}
    results = list(payload.get("results") or [])
    if payload.get("error") and not results:
        return NormalizedResult(
            success=False, action=WEB_RESEARCH_ACTION, error_code="web_research_failed",
            error_message=str(payload.get("error"))[:300],
        )
    return NormalizedResult(
        success=True,
        action=WEB_RESEARCH_ACTION,
        data={
            "query": query,
            "results": results,
            "sources": list(payload.get("sources") or []),
            "provider": "gravitre",
            "evidence_kind": "public_web_research",
            # Web findings are leads to verify, never source-of-record business results.
            "source_of_record": False,
        },
    )


# --------------------------------------------------------------------------- runtime fallback


def is_capability_action(action: str) -> bool:
    from app.capability_ontology.registry import get_capability

    raw = str(action or "").strip()
    return raw.startswith("capability.") or get_capability(raw) is not None


def _connected_hint(ctx: Any, params: dict[str, Any]) -> list[str]:
    hint = [
        str(v).strip().lower()
        for v in (params.pop("_connected_integrations", None) or params.pop("connected_integrations", None) or [])
        if str(v).strip()
    ]
    if not hint and getattr(ctx, "client", None) and getattr(ctx, "org_id", None):
        try:
            from app.services.tool_registry import get_tool_registry

            hint = get_tool_registry().list_connected_integrations(ctx.client, ctx.org_id)
        except Exception:  # noqa: BLE001
            hint = []
    return hint


def ordered_alternatives(
    capability_id: str,
    *,
    connected: list[str],
    blocks: list[Block],
    preferred_vendor: str | None = None,
) -> tuple[list[tuple[str, str]], list[dict[str, Any]]]:
    """(vendor, action) alternatives in preference order, plus the ones skipped and why."""
    from app.capability_ontology.registry import get_capability
    from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
    from app.services.tool_service import list_registered_actions

    definition = get_capability(capability_id)
    if definition is None:
        return [], []
    registered = set(list_registered_actions())
    connected_set = {c.strip().lower() for c in connected if c}
    usable: list[tuple[str, str]] = []
    skipped: list[dict[str, Any]] = []
    for binding in definition.bindings:
        vendor = binding.vendor.strip().lower()
        if vendor not in connected_set:
            continue
        if not catalog_tool_is_implemented(binding.action_key, registered):
            continue
        block = blocked_reason(blocks, binding.action_key)
        if block is not None:
            skipped.append({"vendor": vendor, "action": binding.action_key, "state": block.state, "reason": block.reason})
            continue
        usable.append((vendor, binding.action_key))
    if preferred_vendor:
        usable.sort(key=lambda row: 0 if row[0] == preferred_vendor else 1)
    return usable, skipped


# Readiness ladder, evaluated in order. A provider is EXECUTABLE only when every
# earlier rung holds; the first rung that fails names why it cannot run.
PROVIDER_STATE_LADDER = ("supported", "connected", "authorized", "entitled", "healthy", "executable")
_BLOCK_RUNG = {
    "auth_expired": "authorized",
    "permission_denied": "authorized",
    "plan_limit": "entitled",
    "rate_limited": "healthy",
    "unhealthy": "healthy",
}


def provider_states(
    capability_id: str,
    *,
    connected: list[str],
    blocks: list[Block],
    web_research: bool = False,
) -> list[dict[str, Any]]:
    """Every provider bound to a capability with its readiness ladder, in preference order.

    Planning sees the whole capability universe: a supported provider that is not
    connected still informs the plan (as an optional improvement), but only an
    ``executable`` provider may be run. Authentication, entitlement and health
    are kept apart so "Apollo is connected but its plan does not include people
    search" never reads as "Apollo is disconnected".
    """
    from app.capability_ontology.registry import get_capability
    from app.connectors.action_catalog.tool_aliases import catalog_tool_is_implemented
    from app.services.tool_service import list_registered_actions

    definition = get_capability(capability_id)
    if definition is None:
        return []
    registered = set(list_registered_actions())
    connected_set = {c.strip().lower() for c in connected if c}
    out: list[dict[str, Any]] = []
    for binding in definition.bindings:
        vendor = binding.vendor.strip().lower()
        builtin = binding.action_key == WEB_RESEARCH_ACTION
        rungs = {
            "supported": builtin or catalog_tool_is_implemented(binding.action_key, registered),
            "connected": web_research if builtin else vendor in connected_set,
            "authorized": True,
            "entitled": True,
            "healthy": True,
        }
        block = None if builtin else blocked_reason(blocks, binding.action_key)
        if block is not None:
            rungs[_BLOCK_RUNG.get(block.state, "healthy")] = False
        rungs["executable"] = all(rungs.values())
        state = next((f"not_{r}" for r in PROVIDER_STATE_LADDER if not rungs[r]), "executable")
        out.append(
            {
                "vendor": vendor,
                "action": binding.action_key,
                "label": binding.label,
                "builtin": builtin,
                **rungs,
                "state": state,
                "reason": block.reason if block is not None else None,
                "blockedState": block.state if block is not None else None,
            }
        )
    return out


def invoke_capability_with_fallback(
    ctx: Any,
    action: str,
    params: dict[str, Any],
    *,
    invoke: Callable[[Any, str, dict[str, Any]], Any],
) -> Any:
    """Resolve a capability to a provider and fall back to the next one on a provider refusal."""
    from app.capability_ontology.resolver import resolve_capability
    from app.connectors.action_catalog.tool_aliases import resolve_registry_action
    from app.services.tool_service import list_registered_actions
    from app.services.tool_types import NormalizedResult, ToolError, ToolValidationError

    capability_id = str(action).removeprefix("capability.").strip().lower()
    params = dict(params)
    connected = _connected_hint(ctx, params)
    query = str(params.pop("_capability_query", "") or "")
    classification = params.pop("_capability_classification", None)
    from app.capability_ontology.registry import get_capability

    # Reads fall back in-turn by default: retrying a read on another provider
    # cannot double-apply anything, so a plan-limited or failing provider is
    # replanned around in the same turn on every surface (chat, voice, Plays).
    # Writes still need an explicit opt-in (Play/objective steps set it).
    definition = get_capability(capability_id)
    fallback_flag = params.pop("_capability_fallback", None)
    allow_fallback = (
        bool(fallback_flag)
        if fallback_flag is not None
        else bool(definition is not None and definition.kind == "read")
    )
    blocks = load_blocks(getattr(ctx, "client", None), getattr(ctx, "org_id", None) or "")
    blocked_vendors = {b.vendor for b in blocks if b.action == "*"}

    resolution = resolve_capability(
        capability_id,
        connected_integrations=[c for c in connected if c not in blocked_vendors] or None,
        query=query,
        classification=classification,
        args=params,
    )
    if resolution.ambiguous and not allow_fallback:
        raise ToolValidationError(
            (
                f"Capability '{resolution.capability_id}' is ambiguous across connected systems "
                f"({', '.join(resolution.candidates)}). Specify preferred_vendor or name the system."
            ),
            code="CAPABILITY_AMBIGUOUS",
        )
    alternatives, skipped = ordered_alternatives(
        capability_id, connected=connected, blocks=blocks, preferred_vendor=resolution.resolved_vendor
    )
    research_ok = _binds_web_research(capability_id) and web_research_available(getattr(ctx, "settings", None))
    if not alternatives and research_ok and (allow_fallback or not connected):
        return run_web_research(ctx, capability_id, params)
    if not alternatives:
        detail = "; ".join(f"{s['vendor']} {s['state'].replace('_', ' ')}" for s in skipped)
        raise ToolValidationError(
            f"Capability '{capability_id}' could not be resolved "
            f"({detail or resolution.reason or 'no_connected_implemented_binding'}).",
            code="CAPABILITY_UNRESOLVED",
        )
    if not allow_fallback:
        # Without an explicit opt-in (Play/objective steps set it) only the resolved
        # provider runs; the recorded refusal still lets the next plan route around it.
        alternatives = alternatives[:1]

    registered = set(list_registered_actions())
    attempts: list[dict[str, Any]] = []
    last: Any = None
    for index, (vendor, concrete) in enumerate(alternatives):
        call_params = {
            **params,
            "_capability_resolved_from": capability_id,
            "_capability_resolved_vendor": vendor,
        }
        call_params.pop("preferred_vendor", None)
        resolved = resolve_registry_action(concrete, registered)
        last_one = index == len(alternatives) - 1
        can_research = allow_fallback and research_ok
        try:
            result = invoke(ctx, resolved, call_params)
        except ToolError as exc:
            state = classify_failure(exc)
            if state:
                record_unavailable(ctx.client, ctx.org_id, action=concrete, state=state, reason=str(exc))
            if state is None or (last_one and not can_research):
                raise
            attempts.append({"vendor": vendor, "action": concrete, "state": state})
            continue
        if isinstance(result, NormalizedResult) and not result.success:
            state = classify_failure(result)
            if state and state != "permission_denied":
                record_unavailable(ctx.client, ctx.org_id, action=concrete, state=state, reason=result.error_message)
            if state and (not last_one or can_research):
                attempts.append({"vendor": vendor, "action": concrete, "state": state})
                last = result
                continue
        return _with_fallback_note(result, capability_id, attempts)
    if attempts and allow_fallback and research_ok:
        return _with_fallback_note(run_web_research(ctx, capability_id, params), capability_id, attempts)
    return last


def _with_fallback_note(result: Any, capability_id: str, attempts: list[dict[str, Any]]) -> Any:
    from app.services.tool_types import NormalizedResult

    if attempts and isinstance(result, NormalizedResult):
        result.data = {**(result.data or {}), "capability_fallback": {"capability": capability_id, "skipped": attempts}}
    return result
