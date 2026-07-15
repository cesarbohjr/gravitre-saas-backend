"""Ahrefs agent tool executors (BYO API key — v1 reads)."""
from __future__ import annotations

from typing import Any

from app.connectors.ahrefs_api import (
    AhrefsAPIError,
    backlinks_list,
    domain_rating,
    keywords_list,
    resolve_ahrefs_connector,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: AhrefsAPIError) -> Exception:
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
        cid, api_key = resolve_ahrefs_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "ahrefs", "ahrefs", cid)
    return cid, api_key


def _target_param(params: dict[str, Any]) -> str:
    return str(params.get("target") or params.get("domain") or "").strip()


def _exec_domain_rating(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    target = _target_param(params)
    if not target:
        raise ToolValidationError("ahrefs.domain.rating requires target or domain")
    report_date = str(params.get("date") or params.get("report_date") or "").strip() or None
    try:
        data = domain_rating(api_key, target=target, report_date=report_date)
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.domain.rating", connector_id=cid, data=data)


def _exec_keywords_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    target = _target_param(params)
    if not target:
        raise ToolValidationError("ahrefs.keywords.list requires target or domain")
    country = str(params.get("country") or "us").strip() or "us"
    limit = int(params.get("limit") or 20)
    report_date = str(params.get("date") or params.get("report_date") or "").strip() or None
    try:
        data = keywords_list(
            api_key,
            target=target,
            country=country,
            limit=limit,
            report_date=report_date,
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.keywords.list", connector_id=cid, data=data)


def _exec_backlinks_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    target = _target_param(params)
    if not target:
        raise ToolValidationError("ahrefs.backlinks.list requires target or domain")
    limit = int(params.get("limit") or 20)
    mode = str(params.get("mode") or "subdomains").strip() or "subdomains"
    try:
        data = backlinks_list(api_key, target=target, limit=limit, mode=mode)
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.backlinks.list", connector_id=cid, data=data)


AHREFS_TOOL_EXECUTORS: dict[str, Any] = {
    "ahrefs.backlinks.list": _exec_backlinks_list,
    "ahrefs.keywords.list": _exec_keywords_list,
    "ahrefs.domain.rating": _exec_domain_rating,
}
