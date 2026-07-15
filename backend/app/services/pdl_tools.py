"""People Data Labs agent tool executors (BYO API key — v1 enrich reads)."""
from __future__ import annotations

from typing import Any

from app.connectors.pdl_api import PdlAPIError, company_enrich, person_enrich, resolve_pdl_connector
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: PdlAPIError) -> Exception:
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
        cid, api_key = resolve_pdl_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except PdlAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "pdl", "pdl", cid)
    return cid, api_key


def _enrich_params(params: dict[str, Any]) -> dict[str, Any]:
    """Flatten nested properties or pass through top-level enrich fields."""
    out: dict[str, Any] = {}
    nested = params.get("properties") if isinstance(params.get("properties"), dict) else None
    if nested:
        out.update(nested)
    for key, value in params.items():
        if key in {"connector_id", "properties", "payload"}:
            continue
        out[key] = value
    return out


def _exec_person_enrich(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    try:
        data = person_enrich(api_key, params=_enrich_params(params))
    except PdlAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pdl.person.enrich", connector_id=cid, data=data)


def _exec_company_enrich(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    try:
        data = company_enrich(api_key, params=_enrich_params(params))
    except PdlAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="pdl.company.enrich", connector_id=cid, data=data)


PDL_TOOL_EXECUTORS: dict[str, Any] = {
    "pdl.person.enrich": _exec_person_enrich,
    "pdl.company.enrich": _exec_company_enrich,
}
