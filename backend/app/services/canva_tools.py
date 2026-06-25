"""Canva agent tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.canva_api import (
    CanvaAPIError,
    batch_exports,
    create_autofill,
    create_design,
    create_export,
    delete_design,
    ensure_canva_session,
    get_brand_template,
    get_design,
    get_export,
    list_brand_templates,
    list_designs,
    list_folder_items,
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
        "design_id",
        "designId",
        "folder_id",
        "folderId",
        "export_id",
        "exportId",
        "brand_template_id",
        "brandTemplateId",
        "design_ids",
        "designIds",
        "format_type",
        "formatType",
        "format_options",
        "formatOptions",
        "query",
        "continuation",
        "ownership",
        "sort_by",
        "sortBy",
        "item_types",
        "itemTypes",
        "dataset",
        "limit",
        "payload",
    }
)


def _handle_error(exc: CanvaAPIError) -> Exception:
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
        cid, token = ensure_canva_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "canva", "canva", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


CANVA_TOOL_EXECUTORS: dict[str, Any] = {}


def _register(name: str, fn: Any) -> None:
    CANVA_TOOL_EXECUTORS[name] = fn


def _exec_canva_designs_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_designs(
            token,
            query=params.get("query"),
            continuation=params.get("continuation"),
            ownership=params.get("ownership"),
            sort_by=params.get("sort_by") or params.get("sortBy"),
        )
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.designs.list", connector_id=cid, data=data)


def _exec_canva_designs_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    design_id = params.get("design_id") or params.get("designId")
    if not design_id:
        raise ToolValidationError("canva.designs.get requires design_id")
    try:
        data = get_design(token, str(design_id))
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.designs.get", connector_id=cid, data=data)


def _exec_canva_folders_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    folder_id = params.get("folder_id") or params.get("folderId")
    if not folder_id:
        raise ToolValidationError("canva.folders.list requires folder_id")
    try:
        data = list_folder_items(
            token,
            str(folder_id),
            continuation=params.get("continuation"),
            item_types=params.get("item_types") or params.get("itemTypes"),
            sort_by=params.get("sort_by") or params.get("sortBy"),
        )
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.folders.list", connector_id=cid, data=data)


def _exec_canva_designs_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("canva.designs.create requires a design payload (e.g. design_type, asset_id)")
    try:
        data = create_design(token, payload)
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.designs.create", connector_id=cid, data=data)


def _exec_canva_exports_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    design_id = params.get("design_id") or params.get("designId") or payload.get("design_id")
    if design_id and "design_id" not in payload:
        payload = {**payload, "design_id": design_id}
    if not payload.get("design_id") or not payload.get("format"):
        raise ToolValidationError("canva.exports.create requires design_id and format")
    try:
        data = create_export(token, payload)
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.exports.create", connector_id=cid, data=data)


def _exec_canva_autofill_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("canva.autofill.create requires autofill payload")
    try:
        data = create_autofill(token, payload)
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.autofill.create", connector_id=cid, data=data)


def _exec_canva_brand_templates_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_brand_templates(
            token,
            query=params.get("query"),
            continuation=params.get("continuation"),
            dataset=params.get("dataset"),
            ownership=params.get("ownership"),
            sort_by=params.get("sort_by") or params.get("sortBy"),
        )
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.brand.templates.list", connector_id=cid, data=data)


def _exec_canva_batch_exports(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    design_ids = params.get("design_ids") or params.get("designIds")
    if not isinstance(design_ids, list) or not design_ids:
        raise ToolValidationError("canva.batch.exports requires design_ids array")
    format_type = str(params.get("format_type") or params.get("formatType") or "pdf")
    format_options = params.get("format_options") or params.get("formatOptions")
    if format_options is not None and not isinstance(format_options, dict):
        raise ToolValidationError("canva.batch.exports format_options must be an object")
    try:
        data = batch_exports(
            token,
            design_ids=[str(d) for d in design_ids],
            format_type=format_type,
            format_options=format_options,
        )
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.batch.exports", connector_id=cid, data=data)


def _exec_canva_exports_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    export_id = params.get("export_id") or params.get("exportId")
    if not export_id:
        raise ToolValidationError("canva.exports.get requires export_id")
    try:
        data = get_export(token, str(export_id))
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.exports.get", connector_id=cid, data=data)


def _exec_canva_brand_templates_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    brand_template_id = params.get("brand_template_id") or params.get("brandTemplateId")
    if not brand_template_id:
        raise ToolValidationError("canva.brand.templates.get requires brand_template_id")
    try:
        data = get_brand_template(token, str(brand_template_id))
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.brand.templates.get", connector_id=cid, data=data)


def _exec_canva_designs_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    design_id = params.get("design_id") or params.get("designId")
    if not design_id:
        raise ToolValidationError("canva.designs.delete requires design_id")
    try:
        data = delete_design(token, str(design_id))
    except CanvaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="canva.designs.delete", connector_id=cid, data=data)


_register("canva.designs.list", _exec_canva_designs_list)
_register("canva.designs.get", _exec_canva_designs_get)
_register("canva.folders.list", _exec_canva_folders_list)
_register("canva.designs.create", _exec_canva_designs_create)
_register("canva.exports.create", _exec_canva_exports_create)
_register("canva.autofill.create", _exec_canva_autofill_create)
_register("canva.brand.templates.list", _exec_canva_brand_templates_list)
_register("canva.batch.exports", _exec_canva_batch_exports)
_register("canva.exports.get", _exec_canva_exports_get)
_register("canva.brand.templates.get", _exec_canva_brand_templates_get)
_register("canva.designs.delete", _exec_canva_designs_delete)
