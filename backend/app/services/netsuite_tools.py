"""NetSuite tool executors for invoke_tool (STA-57 / STA-58)."""
from __future__ import annotations

from typing import Any

from app.connectors.netsuite import (
    NetSuiteAPIError,
    create_item_fulfillment,
    create_journal_entry_draft,
    create_sales_order,
    get_customer,
    get_invoice,
    get_item,
    get_sales_order,
    list_invoices,
    update_customer_billing_contact,
)
from app.connectors.netsuite_oauth import ensure_netsuite_session
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolRateLimitedError,
    ToolValidationError,
)


def _enforce_tool_rate_limit(ctx: ToolContext, connector_type: str, connector_id: str) -> None:
    step_type = ctx.step_type or connector_type
    enforce_rate_limit(ctx.client, ctx.org_id, step_type, connector_type, connector_id)


def _netsuite_connector_and_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "netsuite", environment_name=ctx.environment_name)
    if not conn:
        from app.services.tool_types import ToolConnectorNotConnectedError

        raise ToolConnectorNotConnectedError("No active NetSuite connector found for org")
    cid = str(conn["id"])
    _enforce_tool_rate_limit(ctx, "netsuite", cid)
    token, _account_id, api_base, err = ensure_netsuite_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token or not api_base:
        raise ToolAuthExpiredError(err or "NetSuite OAuth not connected")
    return cid, token, api_base


def _handle_netsuite_error(exc: NetSuiteAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_netsuite_customers_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    customer_id = params.get("customer_id") or params.get("customerId")
    if not customer_id:
        raise ToolValidationError("netsuite.customers.get requires customer_id")
    try:
        data = get_customer(api_base, token, str(customer_id))
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.customers.get",
        connector_id=cid,
        data={"customer": data},
    )


def _exec_netsuite_invoices_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    try:
        data = list_invoices(
            api_base,
            token,
            limit=int(params.get("limit") or params.get("max_results") or 25),
            offset=int(params.get("offset") or params.get("start_position") or params.get("startPosition") or 0),
        )
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.invoices.list",
        connector_id=cid,
        data={"items": data.get("items") or data},
    )


def _exec_netsuite_invoices_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    invoice_id = params.get("invoice_id") or params.get("invoiceId")
    if not invoice_id:
        raise ToolValidationError("netsuite.invoices.get requires invoice_id")
    try:
        data = get_invoice(api_base, token, str(invoice_id))
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.invoices.get",
        connector_id=cid,
        data={"invoice": data},
    )


def _exec_netsuite_salesorders_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    sales_order_id = params.get("sales_order_id") or params.get("salesOrderId") or params.get("order_id")
    if not sales_order_id:
        raise ToolValidationError("netsuite.salesorders.get requires sales_order_id")
    try:
        data = get_sales_order(api_base, token, str(sales_order_id))
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.salesorders.get",
        connector_id=cid,
        data={"salesOrder": data},
    )


def _exec_netsuite_items_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    item_id = params.get("item_id") or params.get("itemId")
    if not item_id:
        raise ToolValidationError("netsuite.items.get requires item_id")
    item_type = params.get("item_type") or params.get("itemType")
    try:
        data = get_item(api_base, token, str(item_id), item_type=str(item_type) if item_type else "inventoryItem")
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.items.get",
        connector_id=cid,
        data={"item": data},
    )


def _exec_netsuite_journalentries_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    entry = params.get("entry") or params.get("journal_entry") or params.get("journalEntry")
    if not isinstance(entry, dict) or not entry:
        raise ToolValidationError("netsuite.journalentries.create requires entry object")
    try:
        data = create_journal_entry_draft(api_base, token, entry)
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.journalentries.create",
        connector_id=cid,
        data={"journalEntry": data, "draft": True},
    )


def _exec_netsuite_customers_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    customer_id = params.get("customer_id") or params.get("customerId")
    fields = params.get("fields")
    if not customer_id:
        raise ToolValidationError("netsuite.customers.update requires customer_id")
    if not isinstance(fields, dict) or not fields:
        raise ToolValidationError("netsuite.customers.update requires fields object")
    try:
        data = update_customer_billing_contact(api_base, token, str(customer_id), fields)
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.customers.update",
        connector_id=cid,
        data={"customer": data or {"id": customer_id, "updated": True}},
    )


def _exec_netsuite_salesorders_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    payload = params.get("payload") or params.get("sales_order") or params.get("salesOrder")
    if not isinstance(payload, dict) or not payload:
        raise ToolValidationError("netsuite.salesorders.create requires payload object")
    try:
        data = create_sales_order(api_base, token, payload)
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.salesorders.create",
        connector_id=cid,
        data={"salesOrder": data},
    )


def _exec_netsuite_fulfillment_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _netsuite_connector_and_session(ctx, params)
    payload = params.get("payload") or params.get("fulfillment") or params.get("item_fulfillment")
    if not isinstance(payload, dict) or not payload:
        raise ToolValidationError("netsuite.fulfillment.create requires payload object")
    try:
        data = create_item_fulfillment(api_base, token, payload)
    except NetSuiteAPIError as exc:
        raise _handle_netsuite_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="netsuite.fulfillment.create",
        connector_id=cid,
        data={"itemFulfillment": data},
    )


NETSUITE_TOOL_EXECUTORS: dict[str, Any] = {
    "netsuite.customers.get": _exec_netsuite_customers_get,
    "netsuite.invoices.list": _exec_netsuite_invoices_list,
    "netsuite.invoices.get": _exec_netsuite_invoices_get,
    "netsuite.salesorders.get": _exec_netsuite_salesorders_get,
    "netsuite.items.get": _exec_netsuite_items_get,
    "netsuite.journalentries.create": _exec_netsuite_journalentries_create,
    "netsuite.customers.update": _exec_netsuite_customers_update,
    "netsuite.salesorders.create": _exec_netsuite_salesorders_create,
    "netsuite.fulfillment.create": _exec_netsuite_fulfillment_create,
}
