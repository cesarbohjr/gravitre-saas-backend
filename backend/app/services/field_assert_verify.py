"""Runtime adapter for the ``follow_up_field_assert`` verification mode.

``follow_up_entity_get`` proves an entity exists, which is real proof for a
create and no proof at all for a state change: reading ``deal 42`` back after
``deals.update_stage`` confirms deal 42 exists, not that its stage moved. Those
actions were therefore left on ``accepted_async`` rather than being wired to the
id-based adapter, which would have asserted something untrue.

This mode reads the entity back and compares the *requested* value against the
*stored* value. ``verified=True`` means the vendor is holding the value the user
asked for.

Fails honest, never silent: if the requested value cannot be determined, or the
field is absent from the read-back, the outcome stays ``accepted_async`` with a
specific reason.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.services.entity_get_verify import (
    _clean_id,
    _dict_nodes,
    extract_entity_id,
    id_param_candidates,
)

logger = logging.getLogger(__name__)

_SETTLE_BACKOFF_S = (1.0, 2.0, 4.0)


@dataclass(frozen=True)
class FieldAssertResult:
    verified: bool
    effect: str  # updated | accepted_async | unknown
    detail: str
    read_action: str | None = None
    entity_id: str | None = None
    field: str | None = None
    expected: str | None = None
    observed: str | None = None
    follow_up_attempted: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "effect": self.effect,
            "detail": self.detail,
            "read_action": self.read_action,
            "entity_id": self.entity_id,
            "field": self.field,
            "expected": self.expected,
            "observed": self.observed,
            "follow_up_attempted": self.follow_up_attempted,
        }


def _unverified(detail: str, **kw: Any) -> FieldAssertResult:
    return FieldAssertResult(verified=False, effect="accepted_async", detail=detail, **kw)


def _normalize(value: Any) -> str | None:
    cleaned = _clean_id(value)
    return cleaned.strip().casefold() if cleaned else None


def find_requested_value(
    params: dict[str, Any] | None, request_field: str, assert_field: str
) -> str | None:
    """The value the caller asked for, wherever the vendor wrapper put it."""
    if not isinstance(params, dict):
        return None
    names = [n for n in (request_field, assert_field) if n]
    for node in _dict_nodes(params):
        for name in names:
            found = _clean_id(node.get(name))
            if found:
                return found
    return None


def find_stored_value(payload: dict[str, Any] | None, assert_field: str) -> str | None:
    """The value the vendor is actually holding after the write."""
    if not isinstance(payload, dict) or not assert_field:
        return None
    for node in _dict_nodes(payload):
        found = _clean_id(node.get(assert_field))
        if found:
            return found
    return None


def verify_field_assert(
    *,
    invoke_action: str,
    result_data: dict[str, Any] | None,
    request_params: dict[str, Any] | None,
    ctx: Any = None,
    settle: bool = True,
) -> FieldAssertResult:
    """Confirm a state change by reading the field back and comparing values."""
    from app.services.write_success_verification import resolve_success_verification

    action = str(invoke_action or "").strip().lower()
    if not action:
        return _unverified("no_invoke_action")

    spec = resolve_success_verification(action)
    if spec.mode != "follow_up_field_assert":
        return _unverified("not_field_assert_mode")

    read_action = str(spec.read_action or "").strip()
    assert_field = str(spec.assert_field or "").strip()
    if not read_action or not assert_field:
        return _unverified("incomplete_field_assert_declaration", read_action=read_action or None)

    request_field = str(getattr(spec, "request_field", "") or "").strip()
    expected = find_requested_value(request_params, request_field, assert_field)
    if not expected:
        # Without the requested value there is nothing to assert against, and
        # asserting "the field has some value" would be meaningless.
        return _unverified(
            "requested_value_unavailable", read_action=read_action, field=assert_field
        )

    from app.connectors.action_catalog.tool_aliases import resolve_registry_action
    from app.services.tool_service import invoke_tool, list_registered_actions

    registered = set(list_registered_actions())
    if resolve_registry_action(read_action, registered) not in registered:
        return _unverified(
            "read_action_not_registered",
            read_action=read_action,
            field=assert_field,
            expected=expected,
        )

    entity_id = extract_entity_id(result_data, "id")
    if not entity_id:
        return _unverified(
            "entity_id_absent_from_write_response",
            read_action=read_action,
            field=assert_field,
            expected=expected,
        )
    if ctx is None:
        return _unverified(
            "no_tool_context",
            read_action=read_action,
            entity_id=entity_id,
            field=assert_field,
            expected=expected,
        )

    connector_id = getattr(ctx, "connector_id", None)
    attempted = False
    observed: str | None = None
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
                    observed = find_stored_value(payload, assert_field)
                    if observed is not None and _normalize(observed) == _normalize(expected):
                        return FieldAssertResult(
                            verified=True,
                            effect="updated",
                            detail="follow_up_field_assert_confirmed",
                            read_action=read_action,
                            entity_id=entity_id,
                            field=assert_field,
                            expected=expected,
                            observed=observed,
                            follow_up_attempted=True,
                        )
                    if observed is not None:
                        # The vendor holds a different value — the write did not
                        # take effect as requested. Never report this as success.
                        return FieldAssertResult(
                            verified=False,
                            effect="unknown",
                            detail="field_value_mismatch",
                            read_action=read_action,
                            entity_id=entity_id,
                            field=assert_field,
                            expected=expected,
                            observed=observed,
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
            "field_assert follow-up failed action=%s read=%s err=%s",
            action,
            read_action,
            last_error,
        )
        return _unverified(
            "follow_up_read_failed",
            read_action=read_action,
            entity_id=entity_id,
            field=assert_field,
            expected=expected,
            follow_up_attempted=attempted,
        )
    return _unverified(
        "field_absent_from_read_back",
        read_action=read_action,
        entity_id=entity_id,
        field=assert_field,
        expected=expected,
        follow_up_attempted=attempted,
    )
