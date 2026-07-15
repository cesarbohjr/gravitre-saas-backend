"""SEMrush agent tool executors (BYO API key — v1 reads + v2/v3)."""
from __future__ import annotations

from typing import Any

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.semrush_api import (
    SemrushAPIError,
    add_position_tracking_keywords,
    backlinks_list,
    batch_domain,
    competitors_compare,
    create_project,
    domain_overview,
    exports_run,
    keywords_list,
    resolve_semrush_connector,
)
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: SemrushAPIError) -> Exception:
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
        cid, api_key = resolve_semrush_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "semrush", "semrush", cid)
    return cid, api_key


def _domain_param(params: dict[str, Any]) -> str:
    return str(params.get("domain") or params.get("target") or "").strip()


def _exec_domain_overview(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    domain = _domain_param(params)
    if not domain:
        raise ToolValidationError("semrush.domain.overview requires domain")
    database = str(params.get("database") or "us").strip() or "us"
    try:
        data = domain_overview(api_key, domain=domain, database=database)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.domain.overview", connector_id=cid, data=data)


def _exec_keywords_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    domain = _domain_param(params)
    if not domain:
        raise ToolValidationError("semrush.keywords.list requires domain")
    database = str(params.get("database") or "us").strip() or "us"
    limit = int(params.get("limit") or params.get("display_limit") or 20)
    try:
        data = keywords_list(api_key, domain=domain, database=database, limit=limit)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.keywords.list", connector_id=cid, data=data)


def _exec_backlinks_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    target = _domain_param(params)
    if not target:
        raise ToolValidationError("semrush.backlinks.list requires domain or target")
    target_type = str(params.get("target_type") or "root_domain").strip() or "root_domain"
    limit = int(params.get("limit") or params.get("display_limit") or 20)
    try:
        data = backlinks_list(api_key, target=target, target_type=target_type, limit=limit)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.backlinks.list", connector_id=cid, data=data)


def _exec_projects_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    name = str(params.get("name") or params.get("title") or "").strip()
    properties = params.get("properties") if isinstance(params.get("properties"), dict) else None
    url = str(params.get("project_url") or params.get("url") or "").strip() or None
    try:
        data = create_project(api_key, name=name, url=url, properties=properties)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.projects.create", connector_id=cid, data=data)


def _exec_position_tracking_add(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip()
    keywords = params.get("keywords")
    if keywords is None:
        keywords = params.get("payload")
    if not project_id:
        raise ToolValidationError("semrush.position_tracking.add requires project_id")
    if keywords is None:
        raise ToolValidationError("semrush.position_tracking.add requires keywords")
    try:
        data = add_position_tracking_keywords(api_key, project_id=project_id, keywords=keywords)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="semrush.position_tracking.add", connector_id=cid, data=data
    )


def _exec_batch_domain(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    domains = params.get("domains")
    if not isinstance(domains, list):
        single = _domain_param(params)
        domains = [single] if single else []
    database = str(params.get("database") or "us").strip() or "us"
    try:
        data = batch_domain(api_key, domains=[str(d) for d in domains], database=database)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.batch.domain", connector_id=cid, data=data)


def _exec_competitors_compare(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    domain = _domain_param(params)
    if not domain:
        raise ToolValidationError("semrush.competitors.compare requires domain")
    database = str(params.get("database") or "us").strip() or "us"
    limit = int(params.get("limit") or 10)
    try:
        data = competitors_compare(api_key, domain=domain, database=database, limit=limit)
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.competitors.compare", connector_id=cid, data=data)


def _exec_exports_run(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    domain = _domain_param(params)
    if not domain:
        raise ToolValidationError("semrush.exports.run requires domain")
    database = str(params.get("database") or "us").strip() or "us"
    report_type = str(params.get("report_type") or params.get("type") or "domain_organic").strip()
    limit = int(params.get("limit") or 100)
    try:
        data = exports_run(
            api_key, domain=domain, database=database, report_type=report_type, limit=limit
        )
    except SemrushAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="semrush.exports.run", connector_id=cid, data=data)


SEMRUSH_TOOL_EXECUTORS: dict[str, Any] = {
    "semrush.domain.overview": _exec_domain_overview,
    "semrush.keywords.list": _exec_keywords_list,
    "semrush.backlinks.list": _exec_backlinks_list,
    "semrush.projects.create": _exec_projects_create,
    "semrush.position_tracking.add": _exec_position_tracking_add,
    "semrush.batch.domain": _exec_batch_domain,
    "semrush.competitors.compare": _exec_competitors_compare,
    "semrush.exports.run": _exec_exports_run,
}
