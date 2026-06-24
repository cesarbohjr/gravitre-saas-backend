"""Monday.com tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.monday_api import (
    MondayAPIError,
    batch_create_items,
    create_item,
    create_update,
    delete_item,
    ensure_monday_session,
    get_board,
    get_item,
    list_boards,
    list_users,
    list_workspaces,
    trigger_automation_via_column,
    update_item_column,
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
        "board_id",
        "boardId",
        "item_id",
        "itemId",
        "column_id",
        "columnId",
        "group_id",
        "groupId",
        "item_name",
        "itemName",
        "name",
        "body",
        "value",
        "items",
        "limit",
        "payload",
    }
)


def _handle_error(exc: MondayAPIError) -> Exception:
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
        cid, token = ensure_monday_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "monday", "monday", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


MONDAY_TOOL_EXECUTORS: dict[str, Any] = {}


def _register(name: str, fn: Any) -> None:
    MONDAY_TOOL_EXECUTORS[name] = fn


def _exec_monday_boards_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_boards(token, limit=int(params.get("limit", 50)))
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.boards.list", connector_id=cid, data=data)


def _exec_monday_items_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    item_id = params.get("item_id") or params.get("itemId")
    if not item_id:
        raise ToolValidationError("monday.items.get requires item_id")
    try:
        data = get_item(token, str(item_id))
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.items.get", connector_id=cid, data=data)


def _exec_monday_users_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_users(token)
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.users.list", connector_id=cid, data=data)


def _exec_monday_items_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    board_id = params.get("board_id") or params.get("boardId")
    item_name = params.get("item_name") or params.get("itemName") or params.get("name")
    payload = _payload_from_params(params)
    board_id = board_id or payload.get("board_id") or payload.get("boardId")
    item_name = item_name or payload.get("item_name") or payload.get("name")
    if not board_id or not item_name:
        raise ToolValidationError("monday.items.create requires board_id and item_name")
    try:
        data = create_item(
            token,
            board_id=str(board_id),
            item_name=str(item_name),
            group_id=params.get("group_id") or params.get("groupId") or payload.get("group_id"),
        )
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.items.create", connector_id=cid, data=data)


def _exec_monday_items_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    board_id = params.get("board_id") or params.get("boardId")
    item_id = params.get("item_id") or params.get("itemId")
    column_id = params.get("column_id") or params.get("columnId")
    value = params.get("value")
    payload = _payload_from_params(params)
    board_id = board_id or payload.get("board_id")
    item_id = item_id or payload.get("item_id")
    column_id = column_id or payload.get("column_id")
    if value is None:
        value = payload.get("value")
    if not board_id or not item_id or not column_id or value is None:
        raise ToolValidationError("monday.items.update requires board_id, item_id, column_id, and value")
    try:
        data = update_item_column(
            token,
            board_id=str(board_id),
            item_id=str(item_id),
            column_id=str(column_id),
            value=value,
        )
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.items.update", connector_id=cid, data=data)


def _exec_monday_automations_trigger(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    board_id = params.get("board_id") or params.get("boardId")
    item_id = params.get("item_id") or params.get("itemId")
    column_id = params.get("column_id") or params.get("columnId")
    value = params.get("value")
    if not board_id or not item_id or not column_id or value is None:
        raise ToolValidationError(
            "monday.automations.trigger requires board_id, item_id, column_id, and value (column flip triggers automation)"
        )
    try:
        data = trigger_automation_via_column(
            token,
            board_id=str(board_id),
            item_id=str(item_id),
            column_id=str(column_id),
            value=value,
        )
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.automations.trigger", connector_id=cid, data=data)


def _exec_monday_updates_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    item_id = params.get("item_id") or params.get("itemId")
    body = params.get("body")
    payload = _payload_from_params(params)
    item_id = item_id or payload.get("item_id")
    body = body or payload.get("body")
    if not item_id or not body:
        raise ToolValidationError("monday.updates.create requires item_id and body")
    try:
        data = create_update(token, item_id=str(item_id), body=str(body))
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.updates.create", connector_id=cid, data=data)


def _exec_monday_batch_items(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    board_id = params.get("board_id") or params.get("boardId")
    items = params.get("items")
    if not board_id:
        raise ToolValidationError("monday.batch.items requires board_id")
    if not isinstance(items, list) or not items:
        raise ToolValidationError("monday.batch.items requires items array")
    try:
        data = batch_create_items(token, board_id=str(board_id), items=items)
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.batch.items", connector_id=cid, data=data)


def _exec_monday_items_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    item_id = params.get("item_id") or params.get("itemId")
    if not item_id:
        raise ToolValidationError("monday.items.delete requires item_id")
    try:
        data = delete_item(token, str(item_id))
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.items.delete", connector_id=cid, data=data)


def _exec_monday_boards_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    board_id = params.get("board_id") or params.get("boardId")
    if not board_id:
        raise ToolValidationError("monday.boards.get requires board_id")
    try:
        data = get_board(token, str(board_id))
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.boards.get", connector_id=cid, data=data)


def _exec_monday_workspaces_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_workspaces(token)
    except MondayAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="monday.workspaces.list", connector_id=cid, data=data)


_register("monday.boards.list", _exec_monday_boards_list)
_register("monday.items.get", _exec_monday_items_get)
_register("monday.users.list", _exec_monday_users_list)
_register("monday.items.create", _exec_monday_items_create)
_register("monday.items.update", _exec_monday_items_update)
_register("monday.automations.trigger", _exec_monday_automations_trigger)
_register("monday.updates.create", _exec_monday_updates_create)
_register("monday.batch.items", _exec_monday_batch_items)
_register("monday.items.delete", _exec_monday_items_delete)
_register("monday.boards.get", _exec_monday_boards_get)
_register("monday.workspaces.list", _exec_monday_workspaces_list)
