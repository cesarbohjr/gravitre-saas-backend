"""Pipedrive tool executors (v1–v3 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.pipedrive_api import (
    PipedriveAPIError,
    create_deal,
    create_person,
    ensure_pipedrive_session,
    get_deal,
    get_person,
    list_deals,
    list_organizations,
    list_pipelines,
    search_persons,
    update_deal,
    update_person,
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
        "person_id",
        "personId",
        "deal_id",
        "dealId",
        "term",
        "query",
        "limit",
        "status",
        "stage_id",
        "stageId",
        "payload",
        "properties",
    }
)


def _handle_error(exc: PipedriveAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, token, api_base = ensure_pipedrive_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "pipedrive", "pipedrive", cid)
    return cid, token, api_base


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    for key in ("payload", "properties"):
        payload = params.get(key)
        if isinstance(payload, dict):
            return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


def _exec_pipedrive_persons_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    term = params.get("term") or params.get("query")
    if not term:
        raise ToolValidationError("pipedrive.persons.search requires term")
    try:
        data = search_persons(token, api_base=api_base, term=str(term), limit=int(params.get("limit") or 10))
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.persons.search", connector_id=cid, data=data)


def _exec_pipedrive_persons_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    person_id = params.get("person_id") or params.get("personId")
    if not person_id:
        raise ToolValidationError("pipedrive.persons.get requires person_id")
    try:
        data = get_person(token, api_base=api_base, person_id=str(person_id))
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.persons.get", connector_id=cid, data=data)


def _exec_pipedrive_deals_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    try:
        data = list_deals(
            token,
            api_base=api_base,
            status=params.get("status"),
            limit=int(params.get("limit") or 10),
        )
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.deals.list", connector_id=cid, data=data)


def _exec_pipedrive_deals_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    if not deal_id:
        raise ToolValidationError("pipedrive.deals.get requires deal_id")
    try:
        data = get_deal(token, api_base=api_base, deal_id=str(deal_id))
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.deals.get", connector_id=cid, data=data)


def _exec_pipedrive_organizations_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    try:
        data = list_organizations(token, api_base=api_base, limit=int(params.get("limit") or 10))
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.organizations.list", connector_id=cid, data=data)


def _exec_pipedrive_pipelines_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    try:
        data = list_pipelines(token, api_base=api_base)
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.pipelines.list", connector_id=cid, data=data)


def _exec_pipedrive_persons_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("pipedrive.persons.create requires payload/properties")
    try:
        data = create_person(token, api_base=api_base, payload=payload)
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.persons.create", connector_id=cid, data=data)


def _exec_pipedrive_persons_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    person_id = params.get("person_id") or params.get("personId")
    payload = _payload_from_params(params)
    if not person_id:
        raise ToolValidationError("pipedrive.persons.update requires person_id")
    if not payload:
        raise ToolValidationError("pipedrive.persons.update requires payload/properties")
    try:
        data = update_person(token, api_base=api_base, person_id=str(person_id), payload=payload)
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.persons.update", connector_id=cid, data=data)


def _exec_pipedrive_deals_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("pipedrive.deals.create requires payload/properties")
    try:
        data = create_deal(token, api_base=api_base, payload=payload)
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.deals.create", connector_id=cid, data=data)


def _exec_pipedrive_deals_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    payload = _payload_from_params(params)
    if not deal_id:
        raise ToolValidationError("pipedrive.deals.update requires deal_id")
    if not payload:
        raise ToolValidationError("pipedrive.deals.update requires payload/properties")
    try:
        data = update_deal(token, api_base=api_base, deal_id=str(deal_id), payload=payload)
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.deals.update", connector_id=cid, data=data)


def _exec_pipedrive_deals_update_stage(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _session(ctx, params)
    deal_id = params.get("deal_id") or params.get("dealId")
    stage_id = params.get("stage_id") or params.get("stageId")
    if not deal_id or stage_id is None:
        raise ToolValidationError("pipedrive.deals.update_stage requires deal_id and stage_id")
    try:
        data = update_deal(
            token,
            api_base=api_base,
            deal_id=str(deal_id),
            payload={"stage_id": stage_id},
        )
    except PipedriveAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pipedrive.deals.update_stage", connector_id=cid, data=data)


PIPEDRIVE_TOOL_EXECUTORS = {
    "pipedrive.persons.search": _exec_pipedrive_persons_search,
    "pipedrive.persons.get": _exec_pipedrive_persons_get,
    "pipedrive.deals.list": _exec_pipedrive_deals_list,
    "pipedrive.deals.get": _exec_pipedrive_deals_get,
    "pipedrive.organizations.list": _exec_pipedrive_organizations_list,
    "pipedrive.pipelines.list": _exec_pipedrive_pipelines_list,
    "pipedrive.persons.create": _exec_pipedrive_persons_create,
    "pipedrive.persons.update": _exec_pipedrive_persons_update,
    "pipedrive.deals.create": _exec_pipedrive_deals_create,
    "pipedrive.deals.update": _exec_pipedrive_deals_update,
    "pipedrive.deals.update_stage": _exec_pipedrive_deals_update_stage,
}
