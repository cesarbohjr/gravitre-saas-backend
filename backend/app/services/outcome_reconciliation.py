"""Outcome Ownership — reconcile an uncertain write against the source of record.

When a mutating call fails ambiguously (timeout or dropped connection after the
request left Gravitre), the provider may or may not have applied it. Retrying
blindly can duplicate the side effect; giving up leaves the user's objective
stuck. This module reads the provider back and decides:

* ``applied``      — the record exists / holds the requested values → do not retry;
                     record it as a verified outcome.
* ``not_applied``  — an authoritative read shows the effect is absent → safe to retry.
* ``unknown``      — the source of record could not settle it → stay blocked and
                     tell the user exactly what is unconfirmed.

``not_applied`` is only concluded from a positive, filtered read that returned no
records, never from "the first page did not contain it": an unfiltered list that
happens not to include the record is not proof of absence.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)

ReconciliationState = Literal["applied", "not_applied", "unknown"]

# Natural keys that identify a newly created record, most selective first.
_NATURAL_KEYS = (
    "email",
    "domain",
    "external_id",
    "externalId",
    "sku",
    "phone",
    "name",
    "title",
    "subject",
    "dealname",
)
_ID_ARG_KEYS = ("id", "record_id", "object_id", "contact_id", "company_id", "deal_id", "ticket_id", "entity_id")
_LOOKUP_VERBS = ("search", "find", "query", "list")
_QUERY_PARAM_NAMES = ("query", "q", "search")
# Re-applying these leaves the same end state, so once absence of the requested
# values is shown they may run again.
_IDEMPOTENT_VERBS = ("update", "patch", "set", "upsert", "archive", "delete", "remove", "close")


@dataclass(frozen=True)
class ReconciliationResult:
    state: ReconciliationState
    detail: str
    resource_id: str | None = None
    lookup_action: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "detail": self.detail,
            "resource_id": self.resource_id,
            "lookup_action": self.lookup_action,
            "evidence": dict(self.evidence),
        }


def _flat_args(args: dict[str, Any] | None) -> dict[str, Any]:
    data = dict(args or {})
    props = data.get("properties") if isinstance(data.get("properties"), dict) else {}
    return {**props, **{k: v for k, v in data.items() if k != "properties"}}


def _natural_key(args: dict[str, Any]) -> tuple[str, str] | None:
    flat = _flat_args(args)
    for key in _NATURAL_KEYS:
        value = flat.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return key, str(value).strip()
    return None


def _registered(action: str) -> str | None:
    from app.connectors.action_catalog.tool_aliases import resolve_registry_action
    from app.services.tool_service import list_registered_actions

    registered = set(list_registered_actions())
    resolved = resolve_registry_action(action, registered)
    return resolved if resolved in registered else None


def _node_matches(node: dict[str, Any], key: str, value: str) -> bool:
    target = value.strip().lower()
    props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
    for container in (node, props):
        candidate = container.get(key)
        if isinstance(candidate, (str, int)) and str(candidate).strip().lower() == target:
            return True
    return False


def _records(payload: dict[str, Any]) -> list[dict[str, Any]] | None:
    """The record collection of a lookup response, or None when not list-shaped."""
    for key in ("results", "contacts", "companies", "deals", "items", "records", "data", "rows", "tickets"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return None


def reconcile_uncertain_write(
    *,
    ctx: Any,
    invoke_action: str,
    args: dict[str, Any] | None,
) -> ReconciliationResult:
    """Decide whether an ambiguous write took effect. Never raises."""
    action = str(invoke_action or "").strip().lower()
    parts = action.split(".")
    if len(parts) < 3 or ctx is None:
        return ReconciliationResult("unknown", "unsupported_action_shape")
    vendor, resource, verb = parts[0], parts[1], parts[-1]
    flat = _flat_args(args)
    try:
        record_id = next(
            (str(flat[k]).strip() for k in _ID_ARG_KEYS if isinstance(flat.get(k), (str, int)) and str(flat[k]).strip()),
            None,
        )
        if record_id and any(v in verb for v in _IDEMPOTENT_VERBS):
            return _reconcile_by_id(ctx, vendor, resource, action, record_id, args)
        natural = _natural_key(flat)
        if natural is None:
            return ReconciliationResult("unknown", "no_natural_key_to_search")
        return _reconcile_by_lookup(ctx, vendor, resource, natural)
    except Exception as exc:  # noqa: BLE001
        logger.info("reconcile_uncertain_write_failed action=%s err=%s", action, exc)
        return ReconciliationResult("unknown", f"reconcile_error:{type(exc).__name__}")


def _reconcile_by_id(
    ctx: Any,
    vendor: str,
    resource: str,
    action: str,
    record_id: str,
    args: dict[str, Any] | None,
) -> ReconciliationResult:
    from app.services.outcome_verification import VerificationEvidence, _assert_requested_fields

    read_action = next(
        (a for a in (f"{vendor}.{resource}.get", f"{vendor}.{resource}.retrieve", f"{vendor}.{resource}.read") if _registered(a)),
        None,
    )
    if not read_action:
        return ReconciliationResult("unknown", "no_read_action_for_record")
    base = VerificationEvidence(True, "entity_get", action=action, read_action=read_action, resource_id=record_id)
    checked = _assert_requested_fields(base, ctx=ctx, request_params=args)
    if checked.verified and checked.detail == "follow_up_fields_confirmed":
        return ReconciliationResult(
            "applied", "requested_values_present", record_id, read_action, checked.as_dict()
        )
    if not checked.verified and checked.detail == "requested_field_differs":
        # The change is not present; re-applying an idempotent update is safe.
        return ReconciliationResult(
            "not_applied", "requested_values_absent", record_id, read_action, checked.as_dict()
        )
    return ReconciliationResult("unknown", "record_values_not_comparable", record_id, read_action)


def _reconcile_by_lookup(
    ctx: Any,
    vendor: str,
    resource: str,
    natural: tuple[str, str],
) -> ReconciliationResult:
    from app.services.entity_get_verify import _dict_nodes, extract_entity_id
    from app.services.tool_service import invoke_tool

    key, value = natural
    connector_id = getattr(ctx, "connector_id", None)
    lookups = [a for a in (f"{vendor}.{resource}.{verb}" for verb in _LOOKUP_VERBS) if _registered(a)]
    if not lookups:
        return ReconciliationResult("unknown", "no_lookup_action")
    for lookup in lookups:
        param_sets: list[dict[str, Any]] = [{key: value}] + [{name: value} for name in _QUERY_PARAM_NAMES]
        for params in param_sets:
            if connector_id:
                params = {**params, "connector_id": connector_id}
            out = invoke_tool(ctx, lookup, params)
            if not getattr(out, "success", False):
                continue
            payload = out.data if isinstance(getattr(out, "data", None), dict) else {}
            for node in _dict_nodes(payload):
                if _node_matches(node, key, value):
                    resource_id = extract_entity_id(node)
                    return ReconciliationResult(
                        "applied",
                        f"found_by_{key}",
                        resource_id,
                        lookup,
                        {
                            "verified": True,
                            "method": "reconcile_lookup",
                            "read_action": lookup,
                            "resource_id": resource_id,
                            "field": key,
                            "expected": value,
                            "observed": value,
                        },
                    )
            records = _records(payload)
            if records is not None and not records:
                return ReconciliationResult(
                    "not_applied",
                    f"no_record_with_{key}",
                    None,
                    lookup,
                    {"verified": False, "method": "reconcile_lookup", "read_action": lookup, "field": key, "expected": value},
                )
    return ReconciliationResult("unknown", "lookup_inconclusive", None, lookups[0])
