"""Ahrefs agent tool executors (BYO API key — Site Explorer + Brand Radar)."""
from __future__ import annotations

from typing import Any

from app.connectors.ahrefs_api import (
    AhrefsAPIError,
    add_rank_tracker_keywords,
    backlinks_list,
    brand_radar_competitors_compare,
    brand_radar_exports_run,
    brand_radar_overview,
    brand_radar_prompts_list,
    brand_radar_prompts_track,
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


def _data_sources_param(params: dict[str, Any]) -> list[str] | None:
    raw = params.get("data_sources") or params.get("data_source")
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if str(s).strip()]
    return None


def _exec_brand_radar_overview(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    brand = str(params.get("brand") or params.get("name") or "").strip()
    report_id = str(params.get("report_id") or params.get("report") or "").strip() or None
    country = str(params.get("country") or "us").strip() or "us"
    domain = str(params.get("domain") or params.get("target") or "").strip() or None
    competitors = params.get("competitors")
    if isinstance(competitors, str) and competitors.strip():
        competitors = [competitors.strip()]
    if not isinstance(competitors, list):
        competitors = None
    if not brand and not report_id:
        raise ToolValidationError("ahrefs.brand_radar.overview requires brand or report_id")
    try:
        data = brand_radar_overview(
            api_key,
            brand=brand,
            report_id=report_id,
            country=country,
            domain=domain,
            competitors=competitors,
            data_sources=_data_sources_param(params),
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="ahrefs.brand_radar.overview", connector_id=cid, data=data
    )


def _exec_brand_radar_prompts_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    report_id = str(params.get("report_id") or params.get("report") or "").strip()
    if not report_id:
        raise ToolValidationError("ahrefs.brand_radar.prompts.list requires report_id")
    brand = str(params.get("brand") or params.get("name") or "").strip() or None
    country = str(params.get("country") or "us").strip() or "us"
    prompts = str(params.get("prompts") or "custom").strip() or "custom"
    try:
        data = brand_radar_prompts_list(
            api_key,
            report_id=report_id,
            brand=brand,
            country=country,
            data_sources=_data_sources_param(params),
            prompts=prompts,
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="ahrefs.brand_radar.prompts.list", connector_id=cid, data=data
    )


def _exec_brand_radar_prompts_track(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    report_id = str(params.get("report_id") or params.get("report") or "").strip()
    prompts = params.get("prompts")
    if isinstance(prompts, str) and prompts.strip():
        prompts = [prompts.strip()]
    if not isinstance(prompts, list):
        single = str(params.get("prompt") or "").strip()
        prompts = [single] if single else []
    countries = params.get("countries")
    if isinstance(countries, str) and countries.strip():
        countries = [countries.strip()]
    if not isinstance(countries, list):
        countries = None
    if not report_id:
        raise ToolValidationError("ahrefs.brand_radar.prompts.track requires report_id")
    if not prompts:
        raise ToolValidationError("ahrefs.brand_radar.prompts.track requires prompts")
    try:
        data = brand_radar_prompts_track(
            api_key, report_id=report_id, prompts=[str(p) for p in prompts], countries=countries
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="ahrefs.brand_radar.prompts.track", connector_id=cid, data=data
    )


def _exec_brand_radar_competitors_compare(
    ctx: ToolContext, params: dict[str, Any]
) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    brand = str(params.get("brand") or params.get("name") or "").strip()
    report_id = str(params.get("report_id") or params.get("report") or "").strip() or None
    competitors = params.get("competitors")
    if isinstance(competitors, str) and competitors.strip():
        competitors = [competitors.strip()]
    if not isinstance(competitors, list):
        competitors = []
    country = str(params.get("country") or "us").strip() or "us"
    domain = str(params.get("domain") or params.get("target") or "").strip() or None
    if not brand and not report_id:
        raise ToolValidationError(
            "ahrefs.brand_radar.competitors.compare requires brand or report_id"
        )
    try:
        data = brand_radar_competitors_compare(
            api_key,
            brand=brand,
            competitors=[str(c) for c in competitors],
            report_id=report_id,
            country=country,
            domain=domain,
            data_sources=_data_sources_param(params),
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="ahrefs.brand_radar.competitors.compare",
        connector_id=cid,
        data=data,
    )


def _exec_brand_radar_exports_run(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    report_id = str(params.get("report_id") or params.get("report") or "").strip()
    if not report_id:
        raise ToolValidationError("ahrefs.brand_radar.exports.run requires report_id")
    country = str(params.get("country") or "us").strip() or "us"
    try:
        data = brand_radar_exports_run(
            api_key,
            report_id=report_id,
            country=country,
            data_sources=_data_sources_param(params),
        )
    except AhrefsAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="ahrefs.brand_radar.exports.run", connector_id=cid, data=data
    )


AHREFS_TOOL_EXECUTORS: dict[str, Any] = {
    "ahrefs.backlinks.list": _exec_backlinks_list,
    "ahrefs.keywords.list": _exec_keywords_list,
    "ahrefs.domain.rating": _exec_domain_rating,
    "ahrefs.projects.create": _exec_projects_create,
    "ahrefs.rank_tracker.add": _exec_rank_tracker_add,
    "ahrefs.competitors.compare": _exec_competitors_compare,
    "ahrefs.top_pages.list": _exec_top_pages_list,
    "ahrefs.brand_radar.overview": _exec_brand_radar_overview,
    "ahrefs.brand_radar.prompts.list": _exec_brand_radar_prompts_list,
    "ahrefs.brand_radar.prompts.track": _exec_brand_radar_prompts_track,
    "ahrefs.brand_radar.competitors.compare": _exec_brand_radar_competitors_compare,
    "ahrefs.brand_radar.exports.run": _exec_brand_radar_exports_run,
}
