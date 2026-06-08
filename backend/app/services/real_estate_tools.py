"""Real estate workflow helpers (STA-115)."""
from __future__ import annotations

from typing import Any

from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

MLS_NOTE_SECTIONS = [
    "Property address and legal description",
    "List price, DOM, and showing instructions",
    "Bed/bath/sqft and key features",
    "HOA, taxes, and disclosure summary",
    "Broker remarks and co-broke terms",
]

HANDOFF_CHECKLIST = [
    "Confirm buyer pre-approval and price range",
    "Share MLS sheet and disclosure package",
    "Schedule buyer tour and feedback loop",
    "Align offer strategy with listing agent",
    "Log handoff in CRM with next follow-up date",
]


def _exec_real_estate_mls_note(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    address = str(params.get("property_address") or params.get("propertyAddress") or "123 Main St")
    list_price = str(params.get("list_price") or params.get("listPrice") or "450000")
    sections = [
        {"id": f"mls-{idx + 1}", "title": title, "completed": False}
        for idx, title in enumerate(MLS_NOTE_SECTIONS)
    ]
    return NormalizedResult(
        success=True,
        action="real_estate.mls.note",
        connector_id=params.get("connector_id") or ctx.connector_id,
        data={
            "propertyAddress": address,
            "listPrice": list_price,
            "sections": sections,
            "status": "draft",
        },
    )


def _exec_real_estate_handoff_brief(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    buyer_name = str(params.get("buyer_name") or params.get("buyerName") or "Prospective buyer")
    listing_address = str(params.get("property_address") or params.get("propertyAddress") or "123 Main St")
    checklist = [
        {"id": f"handoff-{idx + 1}", "title": item, "completed": False, "required": True}
        for idx, item in enumerate(HANDOFF_CHECKLIST)
    ]
    return NormalizedResult(
        success=True,
        action="real_estate.handoff.brief",
        connector_id=params.get("connector_id") or ctx.connector_id,
        data={
            "buyerName": buyer_name,
            "propertyAddress": listing_address,
            "checklist": checklist,
            "status": "ready_for_buyer_agent",
        },
    )


REAL_ESTATE_TOOL_EXECUTORS: dict[str, Any] = {
    "real_estate.mls.note": _exec_real_estate_mls_note,
    "real_estate.handoff.brief": _exec_real_estate_handoff_brief,
}
