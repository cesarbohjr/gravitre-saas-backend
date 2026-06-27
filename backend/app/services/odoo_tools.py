"""Odoo agent tool executors (API key auth)."""
from __future__ import annotations

from typing import Any

from app.connectors.odoo import (
    OdooAPIError,
    authenticate,
    batch_upsert_partners,
    confirm_sale_order,
    convert_lead,
    create_invoice,
    create_manufacturing_order,
    create_partner,
    create_sale_order,
    get_partner,
    list_products,
    list_sale_orders,
    post_invoice,
    resolve_odoo_credentials,
    update_partner,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

_RESERVED_BODY_KEYS = frozenset(
    {
        "connector_id",
        "connectorId",
        "partner_id",
        "partnerId",
        "order_id",
        "orderId",
        "move_id",
        "moveId",
        "invoice_id",
        "invoiceId",
        "lead_id",
        "leadId",
        "limit",
        "payload",
        "partners",
    }
)


def _handle_error(exc: OdooAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


def _odoo_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str, int, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, base_url, database, username, api_key = resolve_odoo_credentials(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    uid = authenticate(base_url, database, username, api_key)
    enforce_rate_limit(ctx.client, ctx.org_id, "odoo", "odoo", cid)
    return cid, base_url, database, uid, api_key


def _exec_odoo_partners_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    partner_id = params.get("partner_id") or params.get("partnerId")
    if partner_id is None:
        raise ToolValidationError("odoo.partners.get requires partner_id")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = get_partner(base_url, database, uid, api_key, int(partner_id))
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.partners.get", connector_id=cid, data=data)


def _exec_odoo_sales_orders_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    limit = int(params.get("limit") or 50)
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = list_sale_orders(base_url, database, uid, api_key, limit=limit)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.sales.orders.list", connector_id=cid, data={"orders": data})


def _exec_odoo_inventory_products_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    limit = int(params.get("limit") or 50)
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = list_products(base_url, database, uid, api_key, limit=limit)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="odoo.inventory.products.list",
        connector_id=cid,
        data={"products": data},
    )


def _exec_odoo_partners_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    payload = _payload_from_params(params)
    if not payload.get("name"):
        raise ToolValidationError("odoo.partners.create requires name in payload")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = create_partner(base_url, database, uid, api_key, payload)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.partners.create", connector_id=cid, data=data)


def _exec_odoo_sales_orders_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    payload = _payload_from_params(params)
    if not payload.get("partner_id"):
        raise ToolValidationError("odoo.sales.orders.create requires partner_id in payload")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = create_sale_order(base_url, database, uid, api_key, payload)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.sales.orders.create", connector_id=cid, data=data)


def _exec_odoo_invoices_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    payload = _payload_from_params(params)
    if not payload.get("partner_id"):
        raise ToolValidationError("odoo.invoices.create requires partner_id in payload")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = create_invoice(base_url, database, uid, api_key, payload)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.invoices.create", connector_id=cid, data=data)


def _exec_odoo_manufacturing_orders_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    payload = _payload_from_params(params)
    if not payload.get("product_id"):
        raise ToolValidationError("odoo.manufacturing.orders.create requires product_id in payload")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = create_manufacturing_order(base_url, database, uid, api_key, payload)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="odoo.manufacturing.orders.create",
        connector_id=cid,
        data=data,
    )


def _exec_odoo_crm_leads_convert(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    lead_id = params.get("lead_id") or params.get("leadId")
    if lead_id is None:
        raise ToolValidationError("odoo.crm.leads.convert requires lead_id")
    partner_id = params.get("partner_id") or params.get("partnerId")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = convert_lead(
            base_url,
            database,
            uid,
            api_key,
            int(lead_id),
            partner_id=int(partner_id) if partner_id is not None else None,
        )
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.crm.leads.convert", connector_id=cid, data=data)


def _exec_odoo_batch_partners(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    partners = params.get("partners")
    if partners is None and isinstance(params.get("payload"), dict):
        partners = params["payload"].get("partners")
    if not isinstance(partners, list) or not partners:
        raise ToolValidationError("odoo.batch.partners requires partners array")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = batch_upsert_partners(base_url, database, uid, api_key, partners)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="odoo.batch.partners",
        connector_id=cid,
        data={"partners": data, "count": len(data)},
    )


def _exec_odoo_partners_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    partner_id = params.get("partner_id") or params.get("partnerId")
    payload = _payload_from_params(params)
    if partner_id is None:
        raise ToolValidationError("odoo.partners.update requires partner_id")
    if not payload:
        raise ToolValidationError("odoo.partners.update requires update payload")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = update_partner(base_url, database, uid, api_key, int(partner_id), payload)
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.partners.update", connector_id=cid, data=data)


def _exec_odoo_sales_orders_confirm(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    order_id = params.get("order_id") or params.get("orderId")
    if order_id is None:
        raise ToolValidationError("odoo.sales.orders.confirm requires order_id")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = confirm_sale_order(base_url, database, uid, api_key, int(order_id))
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.sales.orders.confirm", connector_id=cid, data=data)


def _exec_odoo_invoices_post(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    move_id = params.get("move_id") or params.get("moveId") or params.get("invoice_id") or params.get("invoiceId")
    if move_id is None:
        raise ToolValidationError("odoo.invoices.post requires move_id or invoice_id")
    cid, base_url, database, uid, api_key = _odoo_session(ctx, params)
    try:
        data = post_invoice(base_url, database, uid, api_key, int(move_id))
    except OdooAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="odoo.invoices.post", connector_id=cid, data=data)


ODOO_TOOL_EXECUTORS = {
    "odoo.partners.get": _exec_odoo_partners_get,
    "odoo.sales.orders.list": _exec_odoo_sales_orders_list,
    "odoo.inventory.products.list": _exec_odoo_inventory_products_list,
    "odoo.partners.create": _exec_odoo_partners_create,
    "odoo.sales.orders.create": _exec_odoo_sales_orders_create,
    "odoo.invoices.create": _exec_odoo_invoices_create,
    "odoo.manufacturing.orders.create": _exec_odoo_manufacturing_orders_create,
    "odoo.crm.leads.convert": _exec_odoo_crm_leads_convert,
    "odoo.batch.partners": _exec_odoo_batch_partners,
    "odoo.partners.update": _exec_odoo_partners_update,
    "odoo.sales.orders.confirm": _exec_odoo_sales_orders_confirm,
    "odoo.invoices.post": _exec_odoo_invoices_post,
}
