"""Figma agent tool executors (v1–v4 catalog actions)."""
from __future__ import annotations

from typing import Any

from app.connectors.figma_api import (
    FigmaAPIError,
    batch_export_images,
    create_comment,
    create_dev_resource,
    delete_comment,
    ensure_figma_session,
    get_file,
    get_file_meta,
    get_me,
    list_comments,
    list_file_versions,
    list_project_files,
    list_team_projects,
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
        "file_key",
        "fileKey",
        "team_id",
        "teamId",
        "project_id",
        "projectId",
        "comment_id",
        "commentId",
        "node_ids",
        "nodeIds",
        "node_id_groups",
        "nodeIdGroups",
        "ids",
        "format",
        "scale",
        "version",
        "depth",
        "geometry",
        "branch_data",
        "branchData",
        "payload",
    }
)


def _handle_error(exc: FigmaAPIError) -> Exception:
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
        cid, token = ensure_figma_session(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "figma", "figma", cid)
    return cid, token


def _payload_from_params(params: dict[str, Any]) -> dict[str, Any]:
    payload = params.get("payload")
    if isinstance(payload, dict):
        return payload
    return {k: v for k, v in params.items() if k not in _RESERVED_BODY_KEYS and v is not None}


FIGMA_TOOL_EXECUTORS: dict[str, Any] = {}


def _register(name: str, fn: Any) -> None:
    FIGMA_TOOL_EXECUTORS[name] = fn


def _file_key(params: dict[str, Any]) -> str:
    file_key = params.get("file_key") or params.get("fileKey")
    if not file_key:
        raise ToolValidationError("requires file_key")
    return str(file_key)


def _exec_figma_files_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = get_file(
            token,
            _file_key(params),
            version=params.get("version"),
            depth=int(params["depth"]) if params.get("depth") is not None else None,
            geometry=str(params["geometry"]) if params.get("geometry") else None,
        )
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.files.get", connector_id=cid, data=data)


def _exec_figma_files_meta(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = get_file_meta(token, _file_key(params))
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.files.meta", connector_id=cid, data=data)


def _exec_figma_projects_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    team_id = params.get("team_id") or params.get("teamId")
    if not team_id:
        raise ToolValidationError("figma.projects.list requires team_id")
    try:
        data = list_team_projects(token, str(team_id))
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.projects.list", connector_id=cid, data=data)


def _exec_figma_comments_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload.get("message"):
        raise ToolValidationError("figma.comments.create requires message in payload")
    try:
        data = create_comment(token, _file_key(params), payload)
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.comments.create", connector_id=cid, data=data)


def _exec_figma_dev_resources_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    payload = _payload_from_params(params)
    if not payload:
        raise ToolValidationError("figma.dev_resources.create requires dev resource payload")
    try:
        data = create_dev_resource(token, _file_key(params), payload)
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.dev_resources.create", connector_id=cid, data=data)


def _exec_figma_projects_files_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    project_id = params.get("project_id") or params.get("projectId")
    if not project_id:
        raise ToolValidationError("figma.projects.files.list requires project_id")
    branch_data = bool(params.get("branch_data") or params.get("branchData"))
    try:
        data = list_project_files(token, str(project_id), branch_data=branch_data)
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.projects.files.list", connector_id=cid, data=data)


def _exec_figma_comments_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_comments(token, _file_key(params))
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.comments.list", connector_id=cid, data=data)


def _exec_figma_batch_images_export(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    node_id_groups = params.get("node_id_groups") or params.get("nodeIdGroups")
    if not isinstance(node_id_groups, list) or not node_id_groups:
        raise ToolValidationError("figma.batch.images.export requires node_id_groups array of node id lists")
    format_type = str(params.get("format") or "png")
    scale = params.get("scale")
    scale_val = float(scale) if scale is not None else None
    groups: list[list[str]] = []
    for group in node_id_groups:
        if isinstance(group, list):
            groups.append([str(x) for x in group])
        elif isinstance(group, str):
            groups.append([g.strip() for g in group.split(",") if g.strip()])
        else:
            raise ToolValidationError("node_id_groups entries must be arrays or comma-separated strings")
    try:
        data = batch_export_images(
            token,
            file_key=_file_key(params),
            node_id_groups=groups,
            format=format_type,
            scale=scale_val,
        )
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.batch.images.export", connector_id=cid, data=data)


def _exec_figma_comments_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    comment_id = params.get("comment_id") or params.get("commentId")
    if not comment_id:
        raise ToolValidationError("figma.comments.delete requires comment_id")
    try:
        data = delete_comment(token, _file_key(params), str(comment_id))
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.comments.delete", connector_id=cid, data=data)


def _exec_figma_files_versions_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = list_file_versions(token, _file_key(params))
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.files.versions.list", connector_id=cid, data=data)


def _exec_figma_users_me(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _session(ctx, params)
    try:
        data = get_me(token)
    except FigmaAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="figma.users.me", connector_id=cid, data=data)


_register("figma.files.get", _exec_figma_files_get)
_register("figma.files.meta", _exec_figma_files_meta)
_register("figma.projects.list", _exec_figma_projects_list)
_register("figma.comments.create", _exec_figma_comments_create)
_register("figma.dev_resources.create", _exec_figma_dev_resources_create)
_register("figma.projects.files.list", _exec_figma_projects_files_list)
_register("figma.comments.list", _exec_figma_comments_list)
_register("figma.batch.images.export", _exec_figma_batch_images_export)
_register("figma.comments.delete", _exec_figma_comments_delete)
_register("figma.files.versions.list", _exec_figma_files_versions_list)
_register("figma.users.me", _exec_figma_users_me)
