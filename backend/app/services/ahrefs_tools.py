"""Ahrefs agent tool executors (BYO API key — v1 reads + Management writes + v3 reads)."""
from __future__ import annotations

from typing import Any

from app.connectors.ahrefs_api import (
    AhrefsAPIError,
    add_rank_tracker_keywords,
    backlinks_list,
    competitors_compare,
    create_project,
    domain_rating,
    keywords_list,
    resolve_ahrefs_connector,
    top_pages_list,
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


def _exec_projects_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    name = str(params.get("name") or params.get("title") or "").strip()
    url = str(params.get("url") or params.get("project_url") or "").strip()
    properties = params.get("properties") if isinstance(params.get("properties"), dict) else None
    protocol = str(params.get("protocol") or "both").strip() or "both"
    mode = str(params.get("mode") or "subdomains").strip() or "subdomains"
    try:
        data = create_project(
            api_key, name=name, url=url, protocol=protocol, mode=mode, properties=properties
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.projects.create", connector_id=cid, data=data)


def _exec_rank_tracker_add(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip()
    keywords = params.get("keywords")
    if keywords is None:
        keywords = params.get("payload")
    locations = params.get("locations") if isinstance(params.get("locations"), list) else None
    if not project_id:
        raise ToolValidationError("ahrefs.rank_tracker.add requires project_id")
    if keywords is None:
        raise ToolValidationError("ahrefs.rank_tracker.add requires keywords")
    try:
        data = add_rank_tracker_keywords(
            api_key, project_id=project_id, keywords=keywords, locations=locations
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.rank_tracker.add", connector_id=cid, data=data)


def _exec_competitors_compare(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    target = _target_param(params)
    if not target:
        raise ToolValidationError("ahrefs.competitors.compare requires target or domain")
    country = str(params.get("country") or "us").strip() or "us"
    limit = int(params.get("limit") or 10)
    report_date = str(params.get("date") or params.get("report_date") or "").strip() or None
    try:
        data = competitors_compare(
            api_key, target=target, country=country, limit=limit, report_date=report_date
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.competitors.compare", connector_id=cid, data=data)


def _exec_top_pages_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    target = _target_param(params)
    if not target:
        raise ToolValidationError("ahrefs.top_pages.list requires target or domain")
    country = str(params.get("country") or "us").strip() or "us"
    limit = int(params.get("limit") or 20)
    report_date = str(params.get("date") or params.get("report_date") or "").strip() or None
    try:
        data = top_pages_list(
            api_key, target=target, country=country, limit=limit, report_date=report_date
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="ahrefs.top_pages.list", connector_id=cid, data=data)


AHREFS_TOOL_EXECUTORS: dict[str, Any] = {
    "ahrefs.backlinks.list": _exec_backlinks_list,
    "ahrefs.keywords.list": _exec_keywords_list,
    "ahrefs.domain.rating": _exec_domain_rating,
    "ahrefs.projects.create": _exec_projects_create,
    "ahrefs.rank_tracker.add": _exec_rank_tracker_add,
    "ahrefs.competitors.compare": _exec_competitors_compare,
    "ahrefs.top_pages.list": _exec_top_pages_list,
}
