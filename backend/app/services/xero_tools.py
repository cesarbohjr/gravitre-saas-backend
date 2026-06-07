"""Xero tool executors (STA-89)."""
from __future__ import annotations

from typing import Any

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.xero import (
    XeroAPIError,
    ensure_xero_session,
    list_accounts,
    list_contacts,
    list_invoices,
)
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: XeroAPIError) -> Exception:
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
        cid, token, tenant_id = ensure_xero_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except XeroAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "xero", "xero", cid)
    return cid, token, tenant_id


def _exec_xero_contacts_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, tenant_id = _session(ctx, params)
    try:
        data = list_contacts(token, tenant_id)
    except XeroAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="xero.contacts.list", connector_id=cid, data=data)


def _exec_xero_invoices_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, tenant_id = _session(ctx, params)
    try:
        data = list_invoices(token, tenant_id)
    except XeroAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="xero.invoices.list", connector_id=cid, data=data)


def _exec_xero_accounts_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, tenant_id = _session(ctx, params)
    try:
        data = list_accounts(token, tenant_id)
    except XeroAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="xero.accounts.list", connector_id=cid, data=data)


XERO_TOOL_EXECUTORS: dict[str, Any] = {
    "xero.contacts.list": _exec_xero_contacts_list,
    "xero.invoices.list": _exec_xero_invoices_list,
    "xero.accounts.list": _exec_xero_accounts_list,
}
