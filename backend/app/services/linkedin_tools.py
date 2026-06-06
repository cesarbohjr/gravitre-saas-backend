"""LinkedIn prospect enrichment tool executor (STA-63)."""
from __future__ import annotations

from typing import Any

from app.connectors.linkedin import enrich_prospect, load_linkedin_access_token
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.services.tool_types import (
    NormalizedResult,
    ToolContext,
    ToolValidationError,
)


def _enforce_tool_rate_limit(ctx: ToolContext, connector_type: str, connector_id: str) -> None:
    step_type = ctx.step_type or connector_type
    enforce_rate_limit(ctx.client, ctx.org_id, step_type, connector_type, connector_id)


def _linkedin_connector(ctx: ToolContext, params: dict[str, Any]) -> str:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "linkedin", environment_name=ctx.environment_name)
    cid = str(conn["id"]) if conn else ""
    if cid:
        _enforce_tool_rate_limit(ctx, "linkedin", cid)
    return cid


def _exec_linkedin_prospect_enrich(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid = _linkedin_connector(ctx, params)
    token = load_linkedin_access_token(ctx.client, cid, ctx.settings) if cid else None
    data = enrich_prospect(params=params, access_token=token)
    return NormalizedResult(
        success=True,
        action="linkedin.prospect.enrich",
        connector_id=cid or None,
        data=data,
    )


LINKEDIN_TOOL_EXECUTORS: dict[str, Any] = {
    "linkedin.prospect.enrich": _exec_linkedin_prospect_enrich,
}
