"""SEMrush agent tool executors (BYO API key — v1 reads)."""
from __future__ import annotations

from typing import Any

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.semrush_api import (
    SemrushAPIError,
    backlinks_list,
    domain_overview,
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


SEMRUSH_TOOL_EXECUTORS: dict[str, Any] = {
    "semrush.domain.overview": _exec_domain_overview,
    "semrush.keywords.list": _exec_keywords_list,
    "semrush.backlinks.list": _exec_backlinks_list,
}
