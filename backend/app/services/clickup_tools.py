"""ClickUp tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.clickup_api import (
    ClickUpAPIError,
    bulk_update_tasks,
    create_comment,
    create_task,
    create_time_entry,
    create_webhook,
    delete_task,
    ensure_clickup_session,
    get_list,
    get_task,
    list_spaces,
    list_team_members,
    update_goal,
    update_task,
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
        "task_id",
        "taskId",
        "list_id",
        "listId",
        "team_id",
        "teamId",
        "goal_id",
        "goalId",
        "payload",
    }
)


def _handle_error(exc: ClickUpAPIError) -> Exception:
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
        cid, token = ensure_clickup_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "clickup", "clickup", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


def _exec_clickup_tasks_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("clickup.tasks.get requires task_id")
    try:
        data = get_task(token, str(task_id))
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.tasks.get", connector_id=cid, data=data)


def _exec_clickup_tasks_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    from app.connectors.clickup_api import list_tasks

    cid, token = _session(ctx, params)
    team_id = params.get("team_id") or params.get("teamId")
    list_id = params.get("list_id") or params.get("listId")
    include_closed = bool(params.get("include_closed") or params.get("includeClosed"))
    try:
        data = list_tasks(
            token,
            team_id=str(team_id) if team_id else None,
            list_id=str(list_id) if list_id else None,
            include_closed=include_closed,
        )
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.tasks.list", connector_id=cid, data=data)


def _exec_clickup_lists_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    list_id = params.get("list_id") or params.get("listId")
    if not list_id:
        raise ToolValidationError("clickup.lists.get requires list_id")
    try:
        data = get_list(token, str(list_id))
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.lists.get", connector_id=cid, data=data)


def _exec_clickup_spaces_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    team_id = params.get("team_id") or params.get("teamId")
    try:
        data = list_spaces(token, team_id=str(team_id) if team_id else None)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.spaces.list", connector_id=cid, data=data)


def _exec_clickup_tasks_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    list_id = params.get("list_id") or params.get("listId")
    if not list_id:
        raise ToolValidationError("clickup.tasks.create requires list_id")
    payload = _payload_from_params(params)
    if not payload.get("name"):
        raise ToolValidationError("clickup.tasks.create requires name in payload")
    try:
        data = create_task(token, str(list_id), payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.tasks.create", connector_id=cid, data=data)


def _exec_clickup_tasks_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("clickup.tasks.update requires task_id")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("clickup.tasks.update requires update payload")
    try:
        data = update_task(token, str(task_id), payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.tasks.update", connector_id=cid, data=data)


def _exec_clickup_comments_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("clickup.comments.create requires task_id")
    payload = _payload_from_params(params)
    if not payload.get("comment_text") and not payload.get("comment"):
        raise ToolValidationError("clickup.comments.create requires comment_text")
    if "comment_text" not in payload and payload.get("comment"):
        payload = {**payload, "comment_text": payload["comment"]}
    try:
        data = create_comment(token, str(task_id), payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.comments.create", connector_id=cid, data=data)


def _exec_clickup_time_entries_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    team_id = params.get("team_id") or params.get("teamId")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("clickup.time_entries.create requires time entry payload")
    try:
        data = create_time_entry(token, team_id=str(team_id) if team_id else None, payload=payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.time_entries.create", connector_id=cid, data=data)


def _exec_clickup_goals_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    goal_id = params.get("goal_id") or params.get("goalId")
    if not goal_id:
        raise ToolValidationError("clickup.goals.update requires goal_id")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("clickup.goals.update requires update payload")
    try:
        data = update_goal(token, str(goal_id), payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.goals.update", connector_id=cid, data=data)


def _exec_clickup_webhooks_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    team_id = params.get("team_id") or params.get("teamId")
    payload = _payload_from_params(params)
    if not payload.get("endpoint"):
        raise ToolValidationError("clickup.webhooks.create requires endpoint in payload")
    try:
        data = create_webhook(token, team_id=str(team_id) if team_id else None, payload=payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.webhooks.create", connector_id=cid, data=data)


def _exec_clickup_tasks_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("clickup.tasks.delete requires task_id")
    try:
        data = delete_task(token, str(task_id))
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.tasks.delete", connector_id=cid, data=data)


def _exec_clickup_tasks_bulk_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    list_id = params.get("list_id") or params.get("listId")
    if not list_id:
        raise ToolValidationError("clickup.tasks.bulk_update requires list_id")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("clickup.tasks.bulk_update requires bulk payload")
    try:
        data = bulk_update_tasks(token, str(list_id), payload)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.tasks.bulk_update", connector_id=cid, data=data)


def _exec_clickup_members_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    team_id = params.get("team_id") or params.get("teamId")
    try:
        data = list_team_members(token, team_id=str(team_id) if team_id else None)
    except ClickUpAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="clickup.members.list", connector_id=cid, data=data)


CLICKUP_TOOL_EXECUTORS: dict[str, Any] = {
    "clickup.tasks.get": _exec_clickup_tasks_get,
    "clickup.tasks.list": _exec_clickup_tasks_list,
    "clickup.lists.get": _exec_clickup_lists_get,
    "clickup.spaces.list": _exec_clickup_spaces_list,
    "clickup.tasks.create": _exec_clickup_tasks_create,
    "clickup.tasks.update": _exec_clickup_tasks_update,
    "clickup.comments.create": _exec_clickup_comments_create,
    "clickup.time_entries.create": _exec_clickup_time_entries_create,
    "clickup.goals.update": _exec_clickup_goals_update,
    "clickup.webhooks.create": _exec_clickup_webhooks_create,
    "clickup.tasks.delete": _exec_clickup_tasks_delete,
    "clickup.tasks.bulk_update": _exec_clickup_tasks_bulk_update,
    "clickup.members.list": _exec_clickup_members_list,
}
