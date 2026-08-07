"""EngageBay agent tool executors."""
from __future__ import annotations

from typing import Any

from app.connectors.engagebay_api import (
    EngageBayAPIError,
    create_contact,
    create_task,
    get_contact,
    list_deals,
    resolve_engagebay_api_key,
    search_contacts,
    update_contact,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import NormalizedResult, ToolAuthExpiredError, ToolContext, ToolRateLimitedError, ToolValidationError
from app.core.safe_dict import safe_normalize_stored_dict


def _handle_error(exc: EngageBayAPIError) -> Exception:
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
        cid, api_key = resolve_engagebay_api_key(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "engagebay", "engagebay", cid)
    return cid, api_key


def _exec_contacts_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    query = str(params.get("query") or params.get("q") or "").strip() or None
    email = str(params.get("email") or "").strip() or None
    limit = int(params.get("limit") or 25)
    try:
        data = search_contacts(api_key, query=query, email=email, limit=limit)
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="engagebay.contacts.search", connector_id=cid, data=data)


def _exec_contacts_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    contact_id = str(params.get("contact_id") or params.get("id") or "").strip() or None
    email = str(params.get("email") or "").strip() or None
    try:
        data = get_contact(api_key, contact_id=contact_id, email=email)
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="engagebay.contacts.get", connector_id=cid, data=data)


def _exec_contacts_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    payload = safe_normalize_stored_dict(params, key='properties') or safe_normalize_stored_dict(params)
    for key in ("connector_id", "connectorId", "properties"):
        payload.pop(key, None)
    if not payload.get("email") and not params.get("email"):
        raise ToolValidationError("engagebay.contacts.create requires email")
    if params.get("email"):
        payload.setdefault("email", params["email"])
    try:
        data = create_contact(api_key, payload)
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="engagebay.contacts.create", connector_id=cid, data=data)


def _exec_contacts_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    contact_id = str(params.get("contact_id") or params.get("id") or "").strip()
    if not contact_id:
        raise ToolValidationError("engagebay.contacts.update requires contact_id")
    payload = safe_normalize_stored_dict(params, key='properties') or safe_normalize_stored_dict(params)
    for key in ("connector_id", "connectorId", "contact_id", "id", "properties"):
        payload.pop(key, None)
    try:
        data = update_contact(api_key, contact_id, payload)
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="engagebay.contacts.update", connector_id=cid, data=data)


def _exec_deals_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    limit = int(params.get("limit") or 25)
    try:
        data = list_deals(api_key, limit=limit)
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="engagebay.deals.list", connector_id=cid, data=data)


def _exec_tasks_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    payload = {k: v for k, v in params.items() if k not in {"connector_id", "connectorId"}}
    if not payload.get("subject") and not payload.get("name"):
        raise ToolValidationError("engagebay.tasks.create requires subject")
    payload.setdefault("name", payload.get("subject"))
    try:
        data = create_task(api_key, payload)
    except EngageBayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="engagebay.tasks.create", connector_id=cid, data=data)


ENGAGEBAY_TOOL_EXECUTORS: dict[str, Any] = {
    "engagebay.contacts.search": _exec_contacts_search,
    "engagebay.contacts.get": _exec_contacts_get,
    "engagebay.contacts.create": _exec_contacts_create,
    "engagebay.contacts.update": _exec_contacts_update,
    "engagebay.deals.list": _exec_deals_list,
    "engagebay.tasks.create": _exec_tasks_create,
}
