"""ConnectWise Manage tool executors."""
from __future__ import annotations

from typing import Any

from app.connectors.connectwise import ConnectWiseAPIError, create_service_ticket, list_companies
from app.connectors.repository import get_connector
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolValidationError,
)


def _connectwise_auth(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, str]]:
    from app.connectors.connector_tool_auth import resolve_connectwise_auth

    connector_id = params.get("connector_id") or params.get("connectorId")
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    if not conn:
        rows = (
            ctx.client.table("connectors")
            .select("*")
            .eq("org_id", ctx.org_id)
            .eq("type", "connectwise")
            .eq("status", "active")
            .limit(1)
            .execute()
            .data
            or []
        )
        conn = rows[0] if rows else None
    if not conn:
        raise ToolValidationError("No active ConnectWise connector found for org")
    cid = str(conn["id"])
    try:
        creds = resolve_connectwise_auth(ctx.client, ctx.org_id, conn, ctx.settings)
    except ValueError as exc:
        raise ToolValidationError(str(exc)) from exc
    return cid, conn, creds


def _handle_error(exc: ConnectWiseAPIError) -> ToolError:
    status = exc.status_code
    if status in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    if status is not None and 400 <= status < 500:
        return ToolValidationError(str(exc))
    return ToolError(str(exc))


def _exec_connectwise_companies_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _conn, creds = _connectwise_auth(ctx, params)
    try:
        companies = list_companies(
            site_url=creds["site_url"],
            company_id=creds["company_id"],
            public_key=creds["public_key"],
            private_key=creds["private_key"],
            client_id=creds["client_id"],
            page_size=int(params.get("page_size") or params.get("pageSize") or 25),
        )
    except ConnectWiseAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="connectwise.companies.list",
        connector_id=cid,
        data={"companies": companies, "count": len(companies)},
    )


def _exec_connectwise_tickets_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _conn, creds = _connectwise_auth(ctx, params)
    summary = params.get("summary") or params.get("subject")
    board_id = params.get("board_id") or params.get("boardId") or creds.get("default_board_id")
    if not summary or board_id is None:
        raise ToolValidationError("connectwise.tickets.create requires summary and board_id")
    company_record_id = params.get("company_record_id") or params.get("companyRecordId")
    try:
        ticket = create_service_ticket(
            site_url=creds["site_url"],
            company_id=creds["company_id"],
            public_key=creds["public_key"],
            private_key=creds["private_key"],
            client_id=creds["client_id"],
            summary=str(summary),
            board_id=int(board_id),
            company_record_id=int(company_record_id) if company_record_id is not None else None,
            description=params.get("description") or params.get("body"),
            priority_id=int(params["priority_id"]) if params.get("priority_id") is not None else None,
        )
    except ConnectWiseAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="connectwise.tickets.create",
        connector_id=cid,
        data={"ticket": ticket},
    )


CONNECTWISE_TOOL_EXECUTORS = {
    "connectwise.companies.list": _exec_connectwise_companies_list,
    "connectwise.tickets.create": _exec_connectwise_tickets_create,
}
