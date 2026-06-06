"""Demo Acme Tools partner connector handlers (STA-72 / STA-73 sandbox)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.connectors.sdk import get_partner_executor, load_manifest_file, register_from_manifest
from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

logger = logging.getLogger(__name__)

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[4] / "docs" / "integration" / "examples" / "acme-tools" / "manifest.json"
)

_DEMO_TICKETS = [
    {"id": "T-1001", "subject": "OAuth callback 500", "status": "open", "priority": "high"},
    {"id": "T-1002", "subject": "Webhook signature mismatch", "status": "open", "priority": "normal"},
    {"id": "T-1003", "subject": "Rate limit on tickets.list", "status": "closed", "priority": "low"},
]


def _tickets_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    """Return mock tickets for sandbox QA."""
    status_filter = str(params.get("status") or "all").lower()
    limit = int(params.get("limit") or 10)
    tickets = _DEMO_TICKETS
    if status_filter in {"open", "closed"}:
        tickets = [ticket for ticket in tickets if ticket["status"] == status_filter]
    return NormalizedResult(
        success=True,
        action="acme_tools.tickets.list",
        connector_id=params.get("connector_id") or ctx.connector_id,
        data={"tickets": tickets[: max(1, min(limit, 100))], "demo": True},
    )


def _tickets_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    subject = str(params.get("subject") or "").strip()
    body = str(params.get("body") or "").strip()
    if not subject or not body:
        raise ToolValidationError("tickets.create requires subject and body")
    ticket_id = f"T-{1000 + len(_DEMO_TICKETS) + 1}"
    ticket = {
        "id": ticket_id,
        "subject": subject,
        "body": body,
        "status": "open",
        "priority": str(params.get("priority") or "normal"),
    }
    _DEMO_TICKETS.append(ticket)
    return NormalizedResult(
        success=True,
        action="acme_tools.tickets.create",
        connector_id=params.get("connector_id") or ctx.connector_id,
        data={"ticket": ticket, "demo": True},
    )


def ensure_acme_tools_demo_registered() -> None:
    """Register Acme Tools demo handlers once per process."""
    if get_partner_executor("acme_tools.tickets.list"):
        return
    if not _MANIFEST_PATH.is_file():
        logger.warning("acme tools manifest missing at %s", _MANIFEST_PATH)
        return
    manifest = load_manifest_file(_MANIFEST_PATH)
    register_from_manifest(
        manifest,
        {
            "tickets.list": _tickets_list,
            "tickets.create": _tickets_create,
        },
    )
