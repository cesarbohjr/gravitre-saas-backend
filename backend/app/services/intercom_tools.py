"""Intercom tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.intercom_api import (
    IntercomAPIError,
    apply_contact_tags,
    create_contact,
    create_contact_note,
    create_ticket,
    delete_contact,
    ensure_intercom_session,
    get_contact,
    list_companies,
    list_conversations,
    list_tickets,
    reply_to_conversation,
    search_contacts,
    trigger_series_event,
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
        "conversation_id",
        "conversationId",
        "tag_ids",
        "tagIds",
        "starting_after",
        "startingAfter",
        "per_page",
        "perPage",
        "page",
        "payload",
    }
)


def _handle_error(exc: IntercomAPIError) -> Exception:
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
        cid, token = ensure_intercom_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "intercom", "intercom", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


def _exec_intercom_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("intercom.contacts.get requires contact_id")
    try:
        data = get_contact(token, str(contact_id))
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.contacts.get", connector_id=cid, data=data)


def _exec_intercom_conversations_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_conversations(
            token,
            starting_after=params.get("starting_after") or params.get("startingAfter"),
            per_page=int(params["per_page"]) if params.get("per_page") is not None else None,
        )
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.conversations.list", connector_id=cid, data=data)


def _exec_intercom_tickets_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_tickets(
            token,
            starting_after=params.get("starting_after") or params.get("startingAfter"),
            per_page=int(params["per_page"]) if params.get("per_page") is not None else None,
        )
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.tickets.list", connector_id=cid, data=data)


def _exec_intercom_contacts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("intercom.contacts.create requires contact payload")
    try:
        data = create_contact(token, payload)
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.contacts.create", connector_id=cid, data=data)


def _exec_intercom_conversations_reply(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    conversation_id = params.get("conversation_id") or params.get("conversationId")
    if not conversation_id:
        raise ToolValidationError("intercom.conversations.reply requires conversation_id")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("intercom.conversations.reply requires reply payload")
    try:
        data = reply_to_conversation(token, str(conversation_id), payload)
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.conversations.reply", connector_id=cid, data=data)


def _exec_intercom_tickets_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("intercom.tickets.create requires ticket payload")
    try:
        data = create_ticket(token, payload)
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.tickets.create", connector_id=cid, data=data)


def _exec_intercom_tags_apply(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    tag_ids = params.get("tag_ids") or params.get("tagIds")
    if not contact_id:
        raise ToolValidationError("intercom.tags.apply requires contact_id")
    if not tag_ids or not isinstance(tag_ids, list):
        raise ToolValidationError("intercom.tags.apply requires tag_ids array")
    try:
        data = apply_contact_tags(token, str(contact_id), [str(x) for x in tag_ids])
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.tags.apply", connector_id=cid, data=data)


def _exec_intercom_series_trigger(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload.get("event_name"):
        raise ToolValidationError("intercom.series.trigger requires event_name in payload")
    try:
        data = trigger_series_event(token, payload)
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.series.trigger", connector_id=cid, data=data)


def _exec_intercom_notes_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("intercom.notes.create requires contact_id")
    payload = _payload_from_params(params)
    if not payload.get("body") and not payload.get("note"):
        raise ToolValidationError("intercom.notes.create requires body")
    if "body" not in payload and payload.get("note"):
        payload = {**payload, "body": payload["note"]}
    try:
        data = create_contact_note(token, str(contact_id), payload)
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.notes.create", connector_id=cid, data=data)


def _exec_intercom_contacts_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload.get("query"):
        raise ToolValidationError("intercom.contacts.search requires query in payload")
    try:
        data = search_contacts(token, payload)
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.contacts.search", connector_id=cid, data=data)


def _exec_intercom_contacts_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    contact_id = params.get("contact_id") or params.get("contactId")
    if not contact_id:
        raise ToolValidationError("intercom.contacts.delete requires contact_id")
    try:
        data = delete_contact(token, str(contact_id))
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.contacts.delete", connector_id=cid, data=data)


def _exec_intercom_companies_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_companies(
            token,
            page=int(params["page"]) if params.get("page") is not None else None,
            per_page=int(params["per_page"]) if params.get("per_page") is not None else None,
        )
    except IntercomAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="intercom.companies.list", connector_id=cid, data=data)


INTERCOM_TOOL_EXECUTORS: dict[str, Any] = {
    "intercom.contacts.get": _exec_intercom_contacts_get,
    "intercom.conversations.list": _exec_intercom_conversations_list,
    "intercom.tickets.list": _exec_intercom_tickets_list,
    "intercom.contacts.create": _exec_intercom_contacts_create,
    "intercom.conversations.reply": _exec_intercom_conversations_reply,
    "intercom.tickets.create": _exec_intercom_tickets_create,
    "intercom.tags.apply": _exec_intercom_tags_apply,
    "intercom.series.trigger": _exec_intercom_series_trigger,
    "intercom.notes.create": _exec_intercom_notes_create,
    "intercom.contacts.search": _exec_intercom_contacts_search,
    "intercom.contacts.delete": _exec_intercom_contacts_delete,
    "intercom.companies.list": _exec_intercom_companies_list,
}
