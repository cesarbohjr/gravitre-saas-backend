"""Clio read tools + intake/conflict workflow helpers (STA-114)."""
from __future__ import annotations

from typing import Any

from app.connectors.clio import (
    ClioAPIError,
    ensure_clio_session,
    get_contact,
    search_contacts,
    search_matters,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

CONFLICT_CHECKLIST_ITEMS = [
    "Search firm-wide matters for adverse parties and related entities",
    "Review prior representations involving opposing counsel or co-parties",
    "Check corporate family tree and subsidiary conflicts",
    "Document screening results and escalate potential conflicts to partner",
    "Obtain informed consent or waiver when required by ethics rules",
]

INTAKE_TASK_TEMPLATE = [
    {"title": "Complete client intake questionnaire", "assigneeRole": "Intake Coordinator", "dueInDays": 1},
    {"title": "Collect engagement letter and retainer", "assigneeRole": "Intake Coordinator", "dueInDays": 2},
    {"title": "Run conflicts screening workflow", "assigneeRole": "Conflict Review", "dueInDays": 1},
    {"title": "Assign responsible attorney and billing rate", "assigneeRole": "Practice Lead", "dueInDays": 3},
    {"title": "Open matter in Clio and link intake documents", "assigneeRole": "Intake Coordinator", "dueInDays": 3},
]


def _handle_error(exc: ClioAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str | None, bool]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, token, demo = ensure_clio_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except ClioAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "clio", "clio", cid)
    return cid, token, demo


def _exec_clio_contacts_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, demo = _session(ctx, params)
    try:
        data = search_contacts(
            access_token=token,
            demo=demo,
            query=params.get("query") or params.get("name"),
            count=int(params.get("count") or 10),
        )
    except ClioAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clio.contacts.search", connector_id=cid, data=data)


def _exec_clio_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, demo = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("clio.contacts.get requires contact_id")
    try:
        data = get_contact(access_token=token, demo=demo, contact_id=str(contact_id))
    except ClioAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clio.contacts.get", connector_id=cid, data=data)


def _exec_clio_matters_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, demo = _session(ctx, params)
    try:
        data = search_matters(
            access_token=token,
            demo=demo,
            query=params.get("query"),
            client_id=params.get("client_id") or params.get("clientId"),
            count=int(params.get("count") or 10),
        )
    except ClioAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clio.matters.search", connector_id=cid, data=data)


def _exec_clio_conflict_checklist(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _, _ = _session(ctx, params)
    prospect_name = str(params.get("prospect_name") or params.get("prospectName") or "Prospective client")
    matter_type = str(params.get("matter_type") or params.get("matterType") or "General intake")
    checklist = [
        {
            "id": f"conflict-{idx + 1}",
            "title": item,
            "completed": False,
            "required": True,
        }
        for idx, item in enumerate(CONFLICT_CHECKLIST_ITEMS)
    ]
    return NormalizedResult(
        success=True,
        action="clio.conflict.checklist",
        connector_id=cid,
        data={
            "prospectName": prospect_name,
            "matterType": matter_type,
            "checklist": checklist,
            "status": "pending_review",
            "note": "Escalate flagged conflicts to a responsible partner before opening matter.",
        },
    )


def _exec_clio_intake_tasks(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _, _ = _session(ctx, params)
    matter_name = str(params.get("matter_name") or params.get("matterName") or "New intake matter")
    tasks = [
        {
            "id": f"task-{idx + 1}",
            **task,
            "status": "pending",
        }
        for idx, task in enumerate(INTAKE_TASK_TEMPLATE)
    ]
    return NormalizedResult(
        success=True,
        action="clio.intake.tasks",
        connector_id=cid,
        data={
            "matterName": matter_name,
            "tasks": tasks,
            "status": "draft",
        },
    )


CLIO_TOOL_EXECUTORS: dict[str, Any] = {
    "clio.contacts.search": _exec_clio_contacts_search,
    "clio.contacts.get": _exec_clio_contacts_get,
    "clio.matters.search": _exec_clio_matters_search,
    "clio.conflict.checklist": _exec_clio_conflict_checklist,
    "clio.intake.tasks": _exec_clio_intake_tasks,
}
