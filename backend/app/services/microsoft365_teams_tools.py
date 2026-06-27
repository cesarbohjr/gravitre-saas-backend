"""Microsoft 365 Teams + SharePoint tool executors (Graph API)."""
from __future__ import annotations

from typing import Any

from app.connectors.connector_tool_auth import resolve_microsoft365_access_token
from app.connectors.microsoft365 import (
    Microsoft365APIError,
    add_channel_tab,
    add_team_member,
    create_online_meeting,
    delete_drive_item,
    list_channel_messages,
    list_drive_items,
    list_joined_teams,
    list_site_drives,
    list_team_channels,
    post_teams_channel_message,
    search_sharepoint_sites,
    set_user_presence,
    upload_drive_item_content,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.services.tool_types import NormalizedResult, ToolAuthExpiredError, ToolContext, ToolValidationError


def _handle_error(exc: Microsoft365APIError) -> Exception:
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _m365_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "microsoft365", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Microsoft 365 connector found for org")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "microsoft365", "microsoft365", cid)
    token = resolve_microsoft365_access_token(
        ctx.client, ctx.org_id, cid, ctx.settings, environment_name=ctx.environment_name
    )
    if not token:
        raise ToolAuthExpiredError("Microsoft 365 OAuth not connected")
    return cid, token


def _exec_teams_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    try:
        data = list_joined_teams(token)
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.list", connector_id=cid, data=data)


def _exec_teams_channels_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    team_id = params.get("team_id")
    if not team_id:
        raise ToolValidationError("microsoft365.teams.channels.list requires team_id")
    try:
        data = list_team_channels(token, team_id=str(team_id))
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.channels.list", connector_id=cid, data=data)


def _exec_teams_messages_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    team_id = params.get("team_id")
    channel_id = params.get("channel_id")
    if not team_id or not channel_id:
        raise ToolValidationError("microsoft365.teams.messages.list requires team_id and channel_id")
    try:
        data = list_channel_messages(
            token,
            team_id=str(team_id),
            channel_id=str(channel_id),
            top=int(params.get("top") or params.get("limit") or 25),
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.messages.list", connector_id=cid, data=data)


def _exec_teams_messages_send(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    team_id = params.get("team_id")
    channel_id = params.get("channel_id")
    content = params.get("content") or params.get("text")
    if not team_id or not channel_id or not content:
        raise ToolValidationError("microsoft365.teams.messages.send requires team_id, channel_id, content")
    try:
        data = post_teams_channel_message(
            token, team_id=str(team_id), channel_id=str(channel_id), content=str(content)
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.messages.send", connector_id=cid, data=data)


def _exec_teams_meetings_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    subject = params.get("subject") or params.get("title")
    start = params.get("start") or params.get("start_datetime")
    end = params.get("end") or params.get("end_datetime")
    if not subject or not start or not end:
        raise ToolValidationError("microsoft365.teams.meetings.create requires subject, start, end")
    try:
        data = create_online_meeting(token, subject=str(subject), start_datetime=str(start), end_datetime=str(end))
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.meetings.create", connector_id=cid, data=data)


def _exec_teams_tabs_create(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    team_id = params.get("team_id")
    channel_id = params.get("channel_id")
    display_name = params.get("display_name") or params.get("name")
    content_url = params.get("content_url") or params.get("url")
    if not team_id or not channel_id or not display_name or not content_url:
        raise ToolValidationError(
            "microsoft365.teams.tabs.create requires team_id, channel_id, display_name, content_url"
        )
    try:
        data = add_channel_tab(
            token,
            team_id=str(team_id),
            channel_id=str(channel_id),
            display_name=str(display_name),
            content_url=str(content_url),
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.tabs.create", connector_id=cid, data=data)


def _exec_teams_members_add(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    team_id = params.get("team_id")
    user_id = params.get("user_id")
    if not team_id or not user_id:
        raise ToolValidationError("microsoft365.teams.members.add requires team_id and user_id")
    roles = params.get("roles")
    try:
        data = add_team_member(
            token,
            team_id=str(team_id),
            user_id=str(user_id),
            roles=[str(r) for r in roles] if isinstance(roles, list) else None,
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.members.add", connector_id=cid, data=data)


def _exec_teams_presence_set(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    availability = params.get("availability")
    activity = params.get("activity")
    if not availability or not activity:
        raise ToolValidationError("microsoft365.teams.presence.set requires availability and activity")
    try:
        data = set_user_presence(
            token,
            availability=str(availability),
            activity=str(activity),
            expiration_duration=str(params.get("expiration_duration") or "PT1H"),
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.teams.presence.set", connector_id=cid, data=data)


def _exec_sharepoint_sites_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    query = params.get("query") or params.get("q") or "*"
    try:
        data = search_sharepoint_sites(token, query=str(query), top=int(params.get("top") or params.get("limit") or 25))
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.sharepoint.sites.list", connector_id=cid, data=data)


def _exec_sharepoint_drives_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    site_id = params.get("site_id")
    if not site_id:
        raise ToolValidationError("microsoft365.sharepoint.drives.list requires site_id")
    try:
        data = list_site_drives(token, site_id=str(site_id))
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.sharepoint.drives.list", connector_id=cid, data=data)


def _exec_sharepoint_files_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    drive_id = params.get("drive_id")
    if not drive_id:
        raise ToolValidationError("microsoft365.sharepoint.files.list requires drive_id")
    try:
        data = list_drive_items(
            token,
            drive_id=str(drive_id),
            item_id=str(params["item_id"]) if params.get("item_id") else None,
            top=int(params.get("top") or params.get("limit") or 25),
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.sharepoint.files.list", connector_id=cid, data=data)


def _exec_sharepoint_files_upload(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    drive_id = params.get("drive_id")
    filename = params.get("filename") or params.get("name")
    content = params.get("content")
    if not drive_id or not filename or content is None:
        raise ToolValidationError("microsoft365.sharepoint.files.upload requires drive_id, filename, content")
    try:
        data = upload_drive_item_content(
            token,
            drive_id=str(drive_id),
            filename=str(filename),
            content=content,
            parent_item_id=str(params["parent_item_id"]) if params.get("parent_item_id") else None,
        )
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.sharepoint.files.upload", connector_id=cid, data=data)


def _exec_sharepoint_files_delete(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token = _m365_session(ctx, params)
    drive_id = params.get("drive_id")
    item_id = params.get("item_id")
    if not drive_id or not item_id:
        raise ToolValidationError("microsoft365.sharepoint.files.delete requires drive_id and item_id")
    try:
        data = delete_drive_item(token, drive_id=str(drive_id), item_id=str(item_id))
    except Microsoft365APIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="microsoft365.sharepoint.files.delete", connector_id=cid, data=data)


_MICROSOFT365_TEAMS_SHAREPOINT: dict[str, Any] = {
    "microsoft365.teams.list": _exec_teams_list,
    "microsoft365.teams.channels.list": _exec_teams_channels_list,
    "microsoft365.teams.messages.list": _exec_teams_messages_list,
    "microsoft365.teams.messages.send": _exec_teams_messages_send,
    "microsoft365.teams.meetings.create": _exec_teams_meetings_create,
    "microsoft365.teams.tabs.create": _exec_teams_tabs_create,
    "microsoft365.teams.members.add": _exec_teams_members_add,
    "microsoft365.teams.presence.set": _exec_teams_presence_set,
    "microsoft365.sharepoint.sites.list": _exec_sharepoint_sites_list,
    "microsoft365.sharepoint.drives.list": _exec_sharepoint_drives_list,
    "microsoft365.sharepoint.files.list": _exec_sharepoint_files_list,
    "microsoft365.sharepoint.files.upload": _exec_sharepoint_files_upload,
    "microsoft365.sharepoint.files.delete": _exec_sharepoint_files_delete,
}

# Legacy microsoft_teams catalog keys delegate to the same Graph executors.
_MICROSOFT_TEAMS_ALIASES: dict[str, str] = {
    "microsoft_teams.teams.list": "microsoft365.teams.list",
    "microsoft_teams.channels.list": "microsoft365.teams.channels.list",
    "microsoft_teams.messages.list": "microsoft365.teams.messages.list",
    "microsoft_teams.messages.send": "microsoft365.teams.messages.send",
    "microsoft_teams.meetings.create": "microsoft365.teams.meetings.create",
    "microsoft_teams.tabs.create": "microsoft365.teams.tabs.create",
    "microsoft_teams.members.add": "microsoft365.teams.members.add",
    "microsoft_teams.presence.set": "microsoft365.teams.presence.set",
}

MICROSOFT365_TEAMS_SHAREPOINT_TOOLS: dict[str, Any] = dict(_MICROSOFT365_TEAMS_SHAREPOINT)
for legacy_key, canonical in _MICROSOFT_TEAMS_ALIASES.items():
    MICROSOFT365_TEAMS_SHAREPOINT_TOOLS[legacy_key] = _MICROSOFT365_TEAMS_SHAREPOINT[canonical]
