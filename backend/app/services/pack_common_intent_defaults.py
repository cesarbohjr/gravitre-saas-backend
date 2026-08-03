"""Pack-common intent defaults — approve-first for MSP / Prospecting common slots.

Part 3 (MCP-gap): for installed-pack *common* intents, fill defaultable slots
from pack workflow constants so the write gate reaches ``awaiting_confirm``
instead of a clarify loop. Does **not** invent irreducible fields (entity_ids,
ICP filters, which-of-many lists).
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from app.marketplace.workflows.msp_prospecting_list_workflow import (
    DEFAULT_APOLLO_LIST_NAME,
    DEFAULT_HUBSPOT_LIST_NAME,
)
from app.services.chat_connector_models import ConnectorActionPlan

# Pack ids this catalog covers (MSP + Prospecting competitive surface).
PACK_IDS = frozenset({"msp-intelligence-pack", "prospecting-intelligence-pack"})

SOURCE_PACK_DEFAULT = "pack_common_default"

# Messages that imply pack-default list names without naming them.
_OMIT_NAME_LIST_CREATE = re.compile(
    r"\b(create|new|add|make)\s+(?:(?:a|an)\s+)?(?:[\w.-]+\s+){0,3}"
    r"(?:contact\s+|static\s+)?(?:list|group|segment)\b",
    re.I,
)
_NAMED_LIST = re.compile(
    r"(?:named|called|name(?:d)?\s*[:=]?\s*)[\"']?([A-Za-z0-9][\w\s.&/-]{0,80})[\"']?",
    re.I,
)
_AMBIGUOUS_LIST_REF = re.compile(
    r"\b(?:my|the|our)\s+list\b|\benrich\s+my\s+list\b",
    re.I,
)
_MSP_PACK_HINT = re.compile(
    r"\b(?:msp|prospecting|outreach\s+list|managed\s+service)\b",
    re.I,
)
# Planner sometimes treats trailing "in Apollo" / "in HubSpot" as the list name.
_VENDOR_LOCATION_FALSE_NAME = re.compile(
    r"^(?:in|on|via|with|using)\s+"
    r"(?:apollo(?:\.io)?|hubspot|clay|salesforce|crm)\s*$",
    re.I,
)


def _mark_inferred(
    plan: ConnectorActionPlan,
    args: dict[str, Any],
    field: str,
    source: str = SOURCE_PACK_DEFAULT,
) -> ConnectorActionPlan:
    inferred = tuple(dict.fromkeys([*(plan.inferred_fields or ()), field]))
    sources = dict(plan.inference_sources or {})
    sources[field] = source
    return replace(plan, args=args, inferred_fields=inferred, inference_sources=sources)


def _explicit_list_name(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    m = _NAMED_LIST.search(text)
    if m:
        name = str(m.group(1) or "").strip().rstrip(".,;:")
        if name and not _OMIT_NAME_LIST_CREATE.search(name):
            return name[:200]
    # Trailing proper noun after "list" — e.g. "Create HubSpot static list MSPs"
    trail = re.search(
        r"\b(?:list|group|segment)\s+[\"']?([A-Za-z][\w\s.&/-]{0,60})[\"']?\s*$",
        text,
        re.I,
    )
    if trail:
        name = str(trail.group(1) or "").strip().rstrip(".,;:")
        if name.lower() not in {"in", "on", "for", "with", "from", "named", "called"}:
            return name[:200]
    return None


def _scrub_false_name(args: dict[str, Any], message: str) -> dict[str, Any]:
    """Drop names that are clearly the whole user utterance / create phrasing."""
    out = dict(args or {})
    name = str(out.get("name") or "").strip()
    message_text = (message or "").strip()
    if not name:
        return out
    if message_text and name.lower() == message_text.lower():
        out.pop("name", None)
        return out
    if _OMIT_NAME_LIST_CREATE.search(name):
        out.pop("name", None)
    return out


def _apply_apollo_list_create(
    plan: ConnectorActionPlan, *, message: str
) -> ConnectorActionPlan:
    # STA-305 parity — reuse shared enrich so inference_sources stay consistent.
    from app.services.chat_connector_execution_service import enrich_plan_inference_metadata

    plan = enrich_plan_inference_metadata(plan, message=message or "")
    args = dict(plan.args or {})
    name = str(args.get("name") or "").strip()
    if name and _VENDOR_LOCATION_FALSE_NAME.match(name):
        args.pop("name", None)
        args.setdefault("modality", "contacts")
        args["name"] = DEFAULT_APOLLO_LIST_NAME
        # Drop stale inference labels for the false name, then re-mark.
        inferred = tuple(f for f in (plan.inferred_fields or ()) if f != "name")
        sources = {
            k: v for k, v in dict(plan.inference_sources or {}).items() if k != "name"
        }
        plan = replace(plan, args=args, inferred_fields=inferred, inference_sources=sources)
        plan = _mark_inferred(plan, args, "name")
    return plan


def _apply_hubspot_list_create(
    plan: ConnectorActionPlan, *, message: str
) -> ConnectorActionPlan:
    args = _scrub_false_name(dict(plan.args or {}), message)
    explicit = _explicit_list_name(message)
    name = str(args.get("name") or "").strip()
    if explicit and not name:
        args["name"] = explicit[:200]
        plan = _mark_inferred(plan, args, "name", "message_explicit")
        args = dict(plan.args or {})
        name = str(args.get("name") or "").strip()
    elif explicit and name and name.lower() == explicit.lower():
        plan = replace(plan, args=args)
    if not name:
        if _AMBIGUOUS_LIST_REF.search(message or "") and not _MSP_PACK_HINT.search(
            message or ""
        ):
            return replace(plan, args=args)
        args["name"] = DEFAULT_HUBSPOT_LIST_NAME
        plan = _mark_inferred(plan, args, "name")
        args = dict(plan.args or {})
    if not str(args.get("processing_type") or "").strip():
        args["processing_type"] = "MANUAL"
        plan = _mark_inferred(plan, args, "processing_type")
        args = dict(plan.args or {})
    if not str(args.get("object_type_id") or "").strip():
        args["object_type_id"] = "0-1"
        plan = _mark_inferred(plan, args, "object_type_id")
    return plan


def _apply_apollo_lists_add(
    plan: ConnectorActionPlan, *, message: str
) -> ConnectorActionPlan:
    """Default target list name only — never invent contact/entity ids."""
    if _AMBIGUOUS_LIST_REF.search(message or "") and not re.search(
        r"\bmsp\s+prospects\b", message or "", re.I
    ):
        # "Enrich my list" / "add to my list" — irreducible without which-list.
        return plan
    args = dict(plan.args or {})
    has_list = bool(
        str(args.get("list_name") or args.get("name") or "").strip()
        or (isinstance(args.get("label_names"), (list, tuple)) and args.get("label_names"))
    )
    if has_list:
        return plan
    explicit = _explicit_list_name(message)
    list_name = explicit or DEFAULT_APOLLO_LIST_NAME
    # Only apply pack default when message hints MSP/prospecting or omit-name add.
    if not explicit and not _MSP_PACK_HINT.search(message or ""):
        if not re.search(r"\badd\s+(?:contacts?\s+)?to\b", message or "", re.I):
            return plan
    args["list_name"] = list_name
    args.setdefault("label_names", [list_name])
    args.setdefault("modality", "contacts")
    return _mark_inferred(plan, args, "list_name")


def _apply_prospecting_list_defaults(
    plan: ConnectorActionPlan, *, message: str
) -> ConnectorActionPlan:
    """Prospecting / ICP list create — name + modality when omit-name."""
    if str(plan.invoke_action or "") != "apollo.lists.create":
        return plan
    # enrich already applied; ensure modality for ICP phrasing.
    args = dict(plan.args or {})
    if not str(args.get("modality") or "").strip():
        args["modality"] = "contacts"
        plan = _mark_inferred(plan, args, "modality")
    return plan


def apply_pack_common_defaults(
    plan: ConnectorActionPlan,
    *,
    message: str = "",
    org_context: dict[str, Any] | None = None,
) -> ConnectorActionPlan:
    """Fill pack-common defaultable slots before ``missing_params_stage_patch``.

    ``org_context`` is reserved for future Module B entity prefill; unused in v1.
    """
    _ = org_context
    if plan is None:
        return plan
    action = str(plan.invoke_action or "").strip()
    if not action:
        return plan

    if action == "apollo.lists.create":
        plan = _apply_apollo_list_create(plan, message=message)
        return _apply_prospecting_list_defaults(plan, message=message)

    if action == "hubspot.lists.create":
        return _apply_hubspot_list_create(plan, message=message)

    if action == "apollo.lists.add":
        return _apply_apollo_lists_add(plan, message=message)

    # Clay push/sync: never invent ``records``; only label CRM target when blank.
    if action == "clay.crm.sync":
        args = dict(plan.args or {})
        if not str(args.get("crm") or "").strip():
            args["crm"] = "hubspot"
            plan = _mark_inferred(plan, args, "crm")
        return plan

    return plan


def pack_common_default_catalog() -> list[dict[str, Any]]:
    """Declarative catalog for audits / batteries (not runtime routing)."""
    return [
        {
            "pack_ids": sorted(PACK_IDS),
            "invoke_action": "apollo.lists.create",
            "defaults": {
                "name": DEFAULT_APOLLO_LIST_NAME,
                "modality": "contacts",
            },
            "irreducible": [],
        },
        {
            "pack_ids": sorted(PACK_IDS),
            "invoke_action": "hubspot.lists.create",
            "defaults": {
                "name": DEFAULT_HUBSPOT_LIST_NAME,
                "processing_type": "MANUAL",
                "object_type_id": "0-1",
            },
            "irreducible": [],
        },
        {
            "pack_ids": sorted(PACK_IDS),
            "invoke_action": "apollo.lists.add",
            "defaults": {"list_name": DEFAULT_APOLLO_LIST_NAME, "modality": "contacts"},
            "irreducible": ["entity_ids", "contact_ids"],
        },
        {
            "pack_ids": sorted(PACK_IDS),
            "invoke_action": "clay.crm.sync",
            "defaults": {"crm": "hubspot"},
            "irreducible": ["records", "record"],
        },
    ]
