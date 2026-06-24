"""Constant Contact tool executors (v1/v2/v3 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.constant_contact_api import (
    ConstantContactAPIError,
    add_list_memberships,
    apply_contact_tags,
    create_contact,
    create_email_campaign,
    delete_contact,
    ensure_constant_contact_session,
    get_contact,
    list_contact_lists,
    list_contacts,
    list_email_campaigns,
    list_segments,
    schedule_email_campaign,
    update_contact,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

_RESERVED_BODY_KEYS = frozenset(
    {
        "connector_id",
        "contact_id",
        "contactId",
        "campaign_activity_id",
        "campaignActivityId",
        "limit",
        "cursor",
        "email",
        "status",
        "lists",
        "offset",
        "payload",
        "source",
        "list_ids",
        "listIds",
        "tag_ids",
        "tagIds",
        "exclude",
        "scheduled_date",
        "scheduledDate",
        "contact_ids",
        "contactIds",
    }
)


def _handle_error(exc: ConstantContactAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, token = ensure_constant_contact_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "constant_contact", "constant_contact", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


def _exec_constant_contact_contacts_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_contacts(
            token,
            limit=int(params["limit"]) if params.get("limit") is not None else None,
            cursor=params.get("cursor"),
            email=params.get("email"),
            status=params.get("status"),
            lists=params.get("lists"),
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.contacts.list", connector_id=cid, data=data)


def _exec_constant_contact_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("constant_contact.contacts.get requires contact_id")
    try:
        data = get_contact(token, str(contact_id))
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.contacts.get", connector_id=cid, data=data)


def _exec_constant_contact_campaigns_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_email_campaigns(
            token,
            limit=int(params["limit"]) if params.get("limit") is not None else None,
            cursor=params.get("cursor"),
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.campaigns.list", connector_id=cid, data=data)


def _exec_constant_contact_contacts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("constant_contact.contacts.create requires contact payload")
    try:
        data = create_contact(token, payload)
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.contacts.create", connector_id=cid, data=data)


def _exec_constant_contact_contacts_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("constant_contact.contacts.update requires contact_id")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("constant_contact.contacts.update requires contact payload")
    try:
        data = update_contact(token, str(contact_id), payload)
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.contacts.update", connector_id=cid, data=data)


def _exec_constant_contact_campaigns_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload.get("name"):
        raise ToolValidationError("constant_contact.campaigns.create requires name in payload")
    if not payload.get("email_campaign_activities"):
        raise ToolValidationError(
            "constant_contact.campaigns.create requires email_campaign_activities in payload"
        )
    try:
        data = create_email_campaign(token, payload)
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.campaigns.create", connector_id=cid, data=data)


def _exec_constant_contact_lists_add_contacts(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    list_ids = params.get("list_ids") or params.get("listIds")
    source = params.get("source")
    if not isinstance(source, dict):
        contact_ids = params.get("contact_ids") or params.get("contactIds")
        if contact_ids:
            source = {"contact_ids": contact_ids}
    if not isinstance(source, dict):
        raise ToolValidationError("constant_contact.lists.add_contacts requires source or contact_ids")
    if not list_ids or not isinstance(list_ids, list):
        raise ToolValidationError("constant_contact.lists.add_contacts requires list_ids array")
    try:
        data = add_list_memberships(token, source=source, list_ids=[str(x) for x in list_ids])
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="constant_contact.lists.add_contacts",
        connector_id=cid,
        data=data,
    )


def _exec_constant_contact_tags_apply(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    source = params.get("source")
    tag_ids = params.get("tag_ids") or params.get("tagIds")
    if not isinstance(source, dict):
        contact_ids = params.get("contact_ids") or params.get("contactIds")
        list_ids = params.get("list_ids") or params.get("listIds")
        if contact_ids:
            source = {"contact_ids": contact_ids}
        elif list_ids:
            source = {"list_ids": list_ids}
    if not isinstance(source, dict):
        raise ToolValidationError("constant_contact.tags.apply requires source, contact_ids, or list_ids")
    if not tag_ids or not isinstance(tag_ids, list):
        raise ToolValidationError("constant_contact.tags.apply requires tag_ids array")
    exclude = params.get("exclude") if isinstance(params.get("exclude"), dict) else None
    try:
        data = apply_contact_tags(
            token,
            source=source,
            tag_ids=[str(x) for x in tag_ids],
            exclude=exclude,
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="constant_contact.tags.apply", connector_id=cid, data=data)


def _exec_constant_contact_campaigns_schedule(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    campaign_activity_id = params.get("campaign_activity_id") or params.get("campaignActivityId")
    scheduled_date = params.get("scheduled_date") or params.get("scheduledDate")
    if not campaign_activity_id:
        raise ToolValidationError("constant_contact.campaigns.schedule requires campaign_activity_id")
    if scheduled_date is None:
        raise ToolValidationError(
            "constant_contact.campaigns.schedule requires scheduled_date (ISO-8601 or '0' to send now)"
        )
    try:
        data = schedule_email_campaign(
            token,
            str(campaign_activity_id),
            scheduled_date=str(scheduled_date),
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="constant_contact.campaigns.schedule",
        connector_id=cid,
        data=data,
    )


def _exec_constant_contact_contact_lists_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_contact_lists(
            token,
            limit=int(params["limit"]) if params.get("limit") is not None else None,
            cursor=params.get("cursor"),
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="constant_contact.contact_lists.list",
        connector_id=cid,
        data=data,
    )


def _exec_constant_contact_segments_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_segments(
            token,
            limit=int(params["limit"]) if params.get("limit") is not None else None,
            cursor=params.get("cursor"),
        )
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="constant_contact.segments.list",
        connector_id=cid,
        data=data,
    )


def _exec_constant_contact_contacts_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("constant_contact.contacts.delete requires contact_id")
    try:
        data = delete_contact(token, str(contact_id))
    except ConstantContactAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="constant_contact.contacts.delete",
        connector_id=cid,
        data=data,
    )


CONSTANT_CONTACT_TOOL_EXECUTORS: dict[str, Any] = {
    "constant_contact.contacts.list": _exec_constant_contact_contacts_list,
    "constant_contact.contacts.get": _exec_constant_contact_contacts_get,
    "constant_contact.campaigns.list": _exec_constant_contact_campaigns_list,
    "constant_contact.contacts.create": _exec_constant_contact_contacts_create,
    "constant_contact.contacts.update": _exec_constant_contact_contacts_update,
    "constant_contact.campaigns.create": _exec_constant_contact_campaigns_create,
    "constant_contact.lists.add_contacts": _exec_constant_contact_lists_add_contacts,
    "constant_contact.tags.apply": _exec_constant_contact_tags_apply,
    "constant_contact.campaigns.schedule": _exec_constant_contact_campaigns_schedule,
    "constant_contact.contact_lists.list": _exec_constant_contact_contact_lists_list,
    "constant_contact.segments.list": _exec_constant_contact_segments_list,
    "constant_contact.contacts.delete": _exec_constant_contact_contacts_delete,
}
