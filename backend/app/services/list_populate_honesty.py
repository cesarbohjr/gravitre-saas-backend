"""Intent-scoped list membership honesty for Apollo/HubSpot list workflows.

Create-only list workflows remain eligible for COMPLETED when create/find is proven.
Populate-intent runs (MSP list builder, enrich→membership, NL populate language, or
planned lists.add / add_contact steps) must show real membership proof before COMPLETED.

This closes the create-without-add-by-step-type gap for populate intents only —
not a blanket rule on every lists.create.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.connector_outcome_effects import (
    coerce_terminal_status_for_effect,
    is_mutating_action,
)

LIST_CREATE_ACTIONS = frozenset(
    {
        "apollo.lists.create",
        "hubspot.lists.create",
    }
)
LIST_ADD_ACTIONS = frozenset(
    {
        "apollo.lists.add",
        "hubspot.lists.add_contact",
        "marketo.lists.add_to_static_list",
    }
)

# Workflows whose definition requires membership / researched contacts on the list.
POPULATE_WORKFLOW_SLUGS = frozenset(
    {
        "msp-prospecting-list-builder",
        "msp-prospects-clay-hubspot-enrichment",
    }
)

LIST_POPULATE_INTENT = re.compile(
    r"\b("
    r"populate(?:\s+(?:the\s+)?(?:list|segment|group))?"
    r"|list\s+membership"
    r"|lists\.add"
    r"|add_contact"
    r"|add\s+(?:those\s+)?(?:contacts?|people|members?|prospects?)\s+to\s+"
    r"(?:the\s+)?(?:list|segment|group|apollo|hubspot)"
    r"|fill\s+(?:the\s+)?(?:list|segment)"
    r"|researched\s+contacts?"
    # MSP "List Builder" name — not Prospecting Pack's "next membership steps" deferral.
    r"|list[- ]builder"
    r"|ensure\s+.{0,80}list\s+membership"
    r")\b",
    re.IGNORECASE,
)

EMPTY_LIST_PARTIAL_REASON = "list created, 0 contacts added"


def is_list_create_action(action: str | None) -> bool:
    return str(action or "").strip().lower() in LIST_CREATE_ACTIONS


def is_list_add_action(action: str | None) -> bool:
    return str(action or "").strip().lower() in LIST_ADD_ACTIONS


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_count(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return n if n > 0 else 0


def membership_contact_count(payload: dict[str, Any] | None) -> int:
    """Count proven contacts added from an add-step payload or output ref."""
    if not isinstance(payload, dict):
        return 0
    bags = [payload]
    for key in ("data", "structured", "output_snapshot", "membership"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            bags.append(nested)

    for bag in bags:
        for key in ("added_count", "contact_count", "contacts_added", "members_added"):
            n = _int_count(bag.get(key))
            if n:
                return n
        entity_ids = bag.get("entity_ids") or bag.get("contact_ids") or bag.get("ids")
        if isinstance(entity_ids, list):
            n = len([x for x in entity_ids if str(x).strip()])
            if n:
                return n
        if str(bag.get("contact_id") or "").strip():
            return 1
    return 0


def has_list_membership_proof(ref: dict[str, Any] | None) -> bool:
    if not isinstance(ref, dict):
        return False
    action = str(ref.get("invoke_action") or ref.get("action") or "").strip().lower()
    if not is_list_add_action(action):
        return False
    success = ref.get("success")
    status = str(ref.get("status") or "").strip().lower()
    if success is False or status in {"failed", "error", "cancelled"}:
        return False
    return membership_contact_count(ref) > 0


def _text_blob(*parts: Any) -> str:
    chunks: list[str] = []
    for part in parts:
        if part is None:
            continue
        if isinstance(part, dict):
            for key in (
                "message",
                "task",
                "prompt",
                "goal",
                "description",
                "summary",
                "receiver_task",
                "workflow_name",
                "workflow_slug",
                "name",
            ):
                text = str(part.get(key) or "").strip()
                if text:
                    chunks.append(text)
            continue
        text = str(part).strip()
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def _step_mentions_populate(step: dict[str, Any]) -> bool:
    meta = _as_dict(step.get("metadata"))
    snap = _as_dict(step.get("output_snapshot"))
    action = str(
        step.get("invoke_action")
        or snap.get("invoke_action")
        or meta.get("action")
        or step.get("action")
        or ""
    ).strip().lower()
    if is_list_add_action(action):
        return True
    blob = _text_blob(
        step.get("name"),
        step.get("step_name"),
        step.get("description"),
        meta.get("task"),
        meta.get("receiver_task"),
        meta.get("description"),
        snap.get("summary"),
        snap.get("message"),
    )
    if LIST_POPULATE_INTENT.search(blob):
        return True
    if "apollo.lists.add" in blob.lower() or "hubspot.lists.add_contact" in blob.lower():
        return True
    return False


def run_expects_list_population(
    *,
    step_rows: list[dict[str, Any]] | None,
    output_refs: list[dict[str, Any]] | None = None,
    parameters: dict[str, Any] | None = None,
    workflow_name: str | None = None,
    workflow_slug: str | None = None,
) -> bool:
    """True only for populate-intent list work — not create-only Prospecting Pack / LIST_CREATE.

    Legitimate create-only paths (Prospecting Pack scout lists, chat LIST_CREATE_INTENT
    without populate language) return False so COMPLETED remains available when create
    itself is proven.
    """
    params = parameters if isinstance(parameters, dict) else {}
    if params.get("expects_list_population") is True or params.get("list_populate_required") is True:
        return True
    if params.get("expects_list_population") is False or params.get("list_populate_required") is False:
        return False

    slug = str(
        workflow_slug
        or params.get("workflow_slug")
        or params.get("pack_workflow_slug")
        or ""
    ).strip().lower()
    if slug in POPULATE_WORKFLOW_SLUGS:
        return True

    name = str(workflow_name or params.get("workflow_name") or "").strip()
    intent_text = _text_blob(
        params.get("message"),
        params.get("task"),
        params.get("prompt"),
        params.get("goal"),
        name,
        slug,
    )
    if LIST_POPULATE_INTENT.search(intent_text):
        # Pure create-only phrasing can still match LIST_CREATE via "add … list";
        # require populate markers beyond bare create.
        if re.search(
            r"\b(populate|membership|lists\.add|add_contact|researched|fill\s+(?:the\s+)?list|"
            r"add\s+(?:those\s+)?(?:contacts?|people|members?))\b",
            intent_text,
            re.I,
        ):
            return True

    for step in step_rows or []:
        if isinstance(step, dict) and _step_mentions_populate(step):
            return True

    for ref in output_refs or []:
        if not isinstance(ref, dict):
            continue
        if is_list_add_action(str(ref.get("invoke_action") or "")):
            return True
        if LIST_POPULATE_INTENT.search(str(ref.get("summary") or "")):
            return True

    return False


def assess_list_populate_honesty(
    *,
    status: str,
    step_rows: list[dict[str, Any]] | None,
    output_refs: list[dict[str, Any]] | None = None,
    parameters: dict[str, Any] | None = None,
    workflow_name: str | None = None,
    workflow_slug: str | None = None,
) -> tuple[str, str | None]:
    """Downgrade COMPLETED → partial_success when populate intent lacks membership proof.

    Returns (status, reason). Reason is EMPTY_LIST_PARTIAL_REASON when coerced.
    """
    normalized = str(status or "").strip().lower()
    if normalized != "completed":
        return status, None

    refs = list(output_refs or [])
    expects = run_expects_list_population(
        step_rows=step_rows,
        output_refs=refs,
        parameters=parameters,
        workflow_name=workflow_name,
        workflow_slug=workflow_slug,
    )
    if not expects:
        return status, None

    if any(has_list_membership_proof(ref) for ref in refs):
        return status, None

    # Also scan raw step snapshots (add may not have been collected into refs yet).
    for step in step_rows or []:
        if not isinstance(step, dict):
            continue
        snap = _as_dict(step.get("output_snapshot"))
        merged = {
            **snap,
            "invoke_action": snap.get("invoke_action") or step.get("invoke_action"),
            "status": step.get("status"),
            "success": snap.get("success", str(step.get("status") or "").lower() in {"completed", "success"}),
        }
        if has_list_membership_proof(merged):
            return status, None

    # Populate intent without membership proof — create/find alone is never COMPLETED here.
    # (Create-only workflows never reach this branch: expects is False above.)
    return "partial_success", EMPTY_LIST_PARTIAL_REASON


def apply_connector_run_honesty(
    *,
    status: str,
    step_rows: list[dict[str, Any]] | None,
    output_refs: list[dict[str, Any]],
    parameters: dict[str, Any] | None = None,
    workflow_name: str | None = None,
    workflow_slug: str | None = None,
) -> tuple[str, str | None]:
    """Run-level honesty: unproven mutating effects, then list-populate membership gate."""
    coerced = status
    reason: str | None = None

    if str(status or "").strip().lower() == "completed" and output_refs:
        mutating_effects = [
            str(ref.get("outcome_effect") or "")
            for ref in output_refs
            if is_mutating_action(str(ref.get("invoke_action") or ""))
        ]
        if mutating_effects and all(
            effect in {"already_existed", "noop", "accepted_async", "unknown"}
            for effect in mutating_effects
        ):
            worst = next(
                (
                    effect
                    for effect in mutating_effects
                    if effect in {"already_existed", "noop", "accepted_async", "unknown"}
                ),
                "unknown",
            )
            coerced = coerce_terminal_status_for_effect(
                status=status,
                effect=worst or "unknown",
                invoke_action=next(
                    (
                        str(ref.get("invoke_action"))
                        for ref in output_refs
                        if is_mutating_action(str(ref.get("invoke_action") or ""))
                    ),
                    None,
                ),
            )
            if coerced != status:
                reason = (
                    "unproven or idempotent mutating write — not a verified create"
                )

    populate_status, populate_reason = assess_list_populate_honesty(
        status=coerced,
        step_rows=step_rows,
        output_refs=output_refs,
        parameters=parameters,
        workflow_name=workflow_name,
        workflow_slug=workflow_slug,
    )
    if populate_reason:
        coerced, reason = populate_status, populate_reason
    else:
        coerced = populate_status

    # Phase 4 — batch degeneracy across step snapshots / output refs.
    try:
        from app.services.batch_degeneracy import apply_batch_degeneracy_to_status

        payloads: list[Any] = []
        for ref in output_refs or []:
            if isinstance(ref, dict):
                payloads.append(ref)
                nested = ref.get("structured") or ref.get("data") or ref.get("result")
                if nested is not None:
                    payloads.append(nested)
        for step in step_rows or []:
            if isinstance(step, dict):
                snap = step.get("output_snapshot")
                if isinstance(snap, dict):
                    payloads.append(snap)
        invoke = next(
            (
                str(ref.get("invoke_action") or "")
                for ref in (output_refs or [])
                if isinstance(ref, dict) and ref.get("invoke_action")
            ),
            None,
        )
        for payload in payloads:
            flagged_status, deg = apply_batch_degeneracy_to_status(
                status=coerced,
                invoke_action=invoke,
                result_data=payload,
            )
            if deg and deg.flagged:
                return flagged_status, (
                    f"batch_degeneracy:{deg.reason}:{deg.field or 'fields'}"
                )
    except Exception:  # noqa: BLE001
        pass

    return coerced, reason
