"""Runtime adapter for the ``follow_up_entity_get`` verification mode.

The success-verification catalog declares a sibling GET for 75 mutating actions,
but nothing executed them: ``schedule_write_success_verification`` returned early
for every non-membership action, so those declarations were inert and the
outcomes were reported with the same confidence as genuinely verified writes.

This module performs the declared read and confirms the written entity id comes
back. Most read actions have no machine-readable parameter contract
(``ActionSpec.input_schema`` is null and ACTION_PARAMETERS covers 9 of them), so
the id parameter is resolved by convention and the candidates are tried in order.

Fails honest, never silent: anything that cannot be independently confirmed stays
``accepted_async`` with a specific reason. ``verified=True`` requires the read to
return the id that was written.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Entity GETs are usually read-your-write, so this is deliberately much shorter
# than the F6 membership window (~81s), which exists for list-index lag.
_SETTLE_BACKOFF_S = (1.0, 2.0, 4.0)

_NESTED_KEYS = ("data", "structured", "result", "record", "entity", "object")


@dataclass(frozen=True)
class EntityGetVerifyResult:
    verified: bool
    effect: str  # created | accepted_async | unknown
    detail: str
    read_action: str | None = None
    entity_id: str | None = None
    follow_up_attempted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "effect": self.effect,
            "detail": self.detail,
            "read_action": self.read_action,
            "entity_id": self.entity_id,
            "follow_up_attempted": self.follow_up_attempted,
        }


def _unverified(detail: str, *, read_action: str | None = None, entity_id: str | None = None,
                attempted: bool = False) -> EntityGetVerifyResult:
    return EntityGetVerifyResult(
        verified=False,
        effect="accepted_async",
        detail=detail,
        read_action=read_action,
        entity_id=entity_id,
        follow_up_attempted=attempted,
    )


def _singularize(resource: str) -> str:
    if resource.endswith("ies"):
        return resource[:-3] + "y"
    if resource.endswith("ses") or resource.endswith("xes"):
        return resource[:-2]
    if resource.endswith("s") and not resource.endswith("ss"):
        return resource[:-1]
    return resource


def extract_entity_id(data: dict[str, Any] | None, assert_field: str = "id") -> str | None:
    """Find the written entity id, searching common nested result envelopes."""
    if not isinstance(data, dict):
        return None
    field = str(assert_field or "id").strip() or "id"
    bags: list[dict[str, Any]] = [data]
    for key in _NESTED_KEYS:
        nested = data.get(key)
        if isinstance(nested, dict):
            bags.append(nested)
    camel = field.split("_")[0] + "".join(p.title() for p in field.split("_")[1:])
    for bag in bags:
        for candidate in (field, camel, "id", "Id"):
            value = bag.get(candidate)
            if value is None:
                continue
            text = str(value).strip()
            # Guard against booleans/sentinels masquerading as an id.
            if text and text.lower() not in {"true", "false", "none", "null", "0"}:
                return text
    return None


def id_param_candidates(read_action: str) -> list[str]:
    """Convention-derived id parameter names, most specific first."""
    parts = str(read_action or "").split(".")
    if len(parts) < 3:
        return ["id"]
    resource = parts[1]
    singular = _singularize(resource)
    ordered = [f"{singular}_id", "id", f"{singular}Id"]
    seen: set[str] = set()
    out: list[str] = []
    for name in ordered:
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def verify_entity_get(
    *,
    invoke_action: str,
    result_data: dict[str, Any] | None,
    ctx: Any = None,
    settle: bool = True,
) -> EntityGetVerifyResult:
    """Confirm a write by reading the entity back through its declared sibling GET."""
    from app.services.write_success_verification import resolve_success_verification

    action = str(invoke_action or "").strip().lower()
    if not action:
        return _unverified("no_invoke_action")

    spec = resolve_success_verification(action)
    if spec.mode != "follow_up_entity_get":
        return _unverified("not_entity_get_mode")
    read_action = str(spec.read_action or "").strip()
    if not read_action:
        return _unverified("no_read_action_declared")

    from app.services.tool_service import invoke_tool, list_registered_actions

    # invoke_tool resolves aliases itself, so this gate has to resolve the same way
    # or it rejects reads that would in fact execute (google_drive.files.get →
    # drive.files.get). invoke_tool still receives the catalog id: one resolver,
    # one authority.
    from app.connectors.action_catalog.tool_aliases import resolve_registry_action

    registered = set(list_registered_actions())
    if resolve_registry_action(read_action, registered) not in registered:
        return _unverified("read_action_not_registered", read_action=read_action)

    entity_id = extract_entity_id(result_data, spec.assert_field or "id")
    if not entity_id:
        return _unverified(
            "entity_id_absent_from_write_response", read_action=read_action
        )
    if ctx is None:
        return _unverified(
            "no_tool_context", read_action=read_action, entity_id=entity_id
        )

    connector_id = getattr(ctx, "connector_id", None)
    attempted = False
    last_error: Exception | None = None

    for param_name in id_param_candidates(read_action):
        params: dict[str, Any] = {param_name: entity_id}
        if connector_id:
            params["connector_id"] = connector_id

        for attempt, delay in enumerate(_SETTLE_BACKOFF_S):
            try:
                attempted = True
                out = invoke_tool(ctx, read_action, params)
                payload = out.data if isinstance(getattr(out, "data", None), dict) else {}
                if getattr(out, "success", False):
                    returned = extract_entity_id(payload, spec.assert_field or "id")
                    if returned and returned == entity_id:
                        return EntityGetVerifyResult(
                            verified=True,
                            effect="created",
                            detail="follow_up_entity_get_confirmed",
                            read_action=read_action,
                            entity_id=entity_id,
                            follow_up_attempted=True,
                        )
                    if returned:
                        return EntityGetVerifyResult(
                            verified=False,
                            effect="unknown",
                            detail=f"entity_id_mismatch:{returned}",
                            read_action=read_action,
                            entity_id=entity_id,
                            follow_up_attempted=True,
                        )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
            if attempt < len(_SETTLE_BACKOFF_S) - 1 and settle:
                time.sleep(delay)
            if not settle:
                break

    if last_error is not None:
        logger.info(
            "entity_get follow-up failed action=%s read=%s err=%s",
            action,
            read_action,
            last_error,
        )
        return _unverified(
            "follow_up_read_failed", read_action=read_action, entity_id=entity_id,
            attempted=attempted,
        )
    return _unverified(
        "follow_up_read_returned_no_entity",
        read_action=read_action,
        entity_id=entity_id,
        attempted=attempted,
    )
