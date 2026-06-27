"""Asana tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.asana_api import (
    AsanaAPIError,
    add_task_to_project,
    batch_task_updates,
    create_story,
    create_task,
    delete_task,
    ensure_asana_session,
    get_task,
    list_projects,
    list_users,
    list_workspaces,
    move_task_to_section,
    search_tasks,
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
        "project_id",
        "projectId",
        "section_id",
        "sectionId",
        "workspace_id",
        "workspaceId",
        "actions",
        "text",
        "limit",
        "payload",
    }
)


def _handle_error(exc: AsanaAPIError) -> Exception:
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
        cid, token = ensure_asana_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "asana", "asana", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


ASANA_TOOL_EXECUTORS: dict[str, Any] = {}


def _register(name: str, fn: Any) -> None:
    ASANA_TOOL_EXECUTORS[name] = fn


def _exec_asana_tasks_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("asana.tasks.get requires task_id")
    try:
        data = get_task(token, str(task_id))
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.tasks.get", connector_id=cid, data=data)


def _exec_asana_projects_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_projects(
            token,
            workspace_id=params.get("workspace_id") or params.get("workspaceId"),
            limit=int(params["limit"]) if params.get("limit") is not None else None,
        )
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.projects.list", connector_id=cid, data=data)


def _exec_asana_users_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_users(token, workspace_id=params.get("workspace_id") or params.get("workspaceId"))
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.users.list", connector_id=cid, data=data)


def _exec_asana_tasks_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload.get("name"):
        raise ToolValidationError("asana.tasks.create requires name in payload")
    try:
        data = create_task(token, payload)
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.tasks.create", connector_id=cid, data=data)


def _exec_asana_tasks_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("asana.tasks.update requires task_id")
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("asana.tasks.update requires update payload")
    try:
        data = update_task(token, str(task_id), payload)
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.tasks.update", connector_id=cid, data=data)


def _exec_asana_stories_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("asana.stories.create requires task_id")
    payload = _payload_from_params(params)
    if not payload.get("text") and not payload.get("html_text"):
        raise ToolValidationError("asana.stories.create requires text in payload")
    try:
        data = create_story(token, str(task_id), payload)
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.stories.create", connector_id=cid, data=data)


def _exec_asana_tasks_add_project(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    project_id = params.get("project_id") or params.get("projectId")
    if not task_id or not project_id:
        raise ToolValidationError("asana.tasks.add_project requires task_id and project_id")
    try:
        data = add_task_to_project(
            token,
            str(task_id),
            project_id=str(project_id),
            section_id=params.get("section_id") or params.get("sectionId"),
        )
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.tasks.add_project", connector_id=cid, data=data)


def _exec_asana_sections_move(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    section_id = params.get("section_id") or params.get("sectionId")
    task_id = params.get("task_id") or params.get("taskId")
    if not section_id or not task_id:
        raise ToolValidationError("asana.sections.move requires section_id and task_id")
    try:
        data = move_task_to_section(token, str(section_id), str(task_id))
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.sections.move", connector_id=cid, data=data)


def _exec_asana_batch_tasks(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    actions = params.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ToolValidationError("asana.batch.tasks requires actions array")
    try:
        data = batch_task_updates(token, actions)
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.batch.tasks", connector_id=cid, data=data)


def _exec_asana_tasks_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    task_id = params.get("task_id") or params.get("taskId")
    if not task_id:
        raise ToolValidationError("asana.tasks.delete requires task_id")
    try:
        data = delete_task(token, str(task_id))
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.tasks.delete", connector_id=cid, data=data)


def _exec_asana_workspaces_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_workspaces(token)
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.workspaces.list", connector_id=cid, data=data)


def _exec_asana_tasks_search(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    workspace_id = params.get("workspace_id") or params.get("workspaceId")
    if not workspace_id:
        raise ToolValidationError("asana.tasks.search requires workspace_id")
    try:
        data = search_tasks(
            token,
            str(workspace_id),
            text=params.get("text"),
            limit=int(params["limit"]) if params.get("limit") is not None else None,
        )
    except AsanaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="asana.tasks.search", connector_id=cid, data=data)


_register("asana.tasks.get", _exec_asana_tasks_get)
_register("asana.projects.list", _exec_asana_projects_list)
_register("asana.users.list", _exec_asana_users_list)
_register("asana.tasks.create", _exec_asana_tasks_create)
_register("asana.tasks.update", _exec_asana_tasks_update)
_register("asana.stories.create", _exec_asana_stories_create)
_register("asana.tasks.add_project", _exec_asana_tasks_add_project)
_register("asana.sections.move", _exec_asana_sections_move)
_register("asana.batch.tasks", _exec_asana_batch_tasks)
_register("asana.tasks.delete", _exec_asana_tasks_delete)
_register("asana.workspaces.list", _exec_asana_workspaces_list)
_register("asana.tasks.search", _exec_asana_tasks_search)
