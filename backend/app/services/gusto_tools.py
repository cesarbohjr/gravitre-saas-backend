"""Gusto v1 read stubs (HR H3).

No gusto connector OAuth helpers exist yet — fail closed with partner-OAuth guidance.
Keep UI partner gate honest (PARTNER_GATED / partner_oauth); vendor shipped=False.
"""
from __future__ import annotations

from typing import Any

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type, get_decrypted_secret
from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError

GUSTO_PARTNER_MSG = (
    "Gusto requires partner OAuth connection — request partner approval and connect "
    "Gusto from Connectors before invoking payroll/HRIS reads"
)


def _resolve_gusto_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(
            ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name
        )
    else:
        conn = get_connector_by_type(
            ctx.client, ctx.org_id, "gusto", environment_name=ctx.environment_name
        )
    if not conn:
        raise ToolValidationError(GUSTO_PARTNER_MSG)
    cid = str(conn["id"])
    status = str(conn.get("status") or "").lower()
    if status not in {"active", "connected", "healthy"}:
        raise ToolValidationError(GUSTO_PARTNER_MSG)
    token = (
        get_decrypted_secret(ctx.client, cid, "access_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "oauth_access_token", ctx.settings)
        or get_decrypted_secret(ctx.client, cid, "api_token", ctx.settings)
    )
    if not token:
        raise ToolValidationError(GUSTO_PARTNER_MSG)
    enforce_rate_limit(ctx.client, ctx.org_id, "gusto", "gusto", cid)
    return cid, token.strip()


def _exec_companies_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    # No Gusto REST client in-repo yet — session check only, then clear gap message.
    _resolve_gusto_session(ctx, params)
    raise ToolValidationError(
        "Gusto companies.get is staged but the partner OAuth API client is not wired yet — "
        "connect Gusto via partner OAuth when available"
    )


def _exec_employees_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    _resolve_gusto_session(ctx, params)
    employee_id = str(params.get("employee_id") or params.get("id") or "").strip()
    if not employee_id:
        raise ToolValidationError("gusto.employees.get requires employee_id")
    raise ToolValidationError(
        "Gusto employees.get is staged but the partner OAuth API client is not wired yet — "
        "connect Gusto via partner OAuth when available"
    )


def _exec_payrolls_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    _resolve_gusto_session(ctx, params)
    raise ToolValidationError(
        "Gusto payrolls.list is staged but the partner OAuth API client is not wired yet — "
        "connect Gusto via partner OAuth when available"
    )


GUSTO_TOOL_EXECUTORS: dict[str, Any] = {
    "gusto.companies.get": _exec_companies_get,
    "gusto.employees.get": _exec_employees_get,
    "gusto.payrolls.list": _exec_payrolls_list,
}
