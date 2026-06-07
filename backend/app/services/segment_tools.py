"""Segment tool executors for agent/workflow invoke (STA-68)."""
from __future__ import annotations

from typing import Any

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.connectors.segment_api import (
    SegmentAPIError,
    group,
    identify,
    resolve_segment_write_key,
    track,
)
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

ToolExecutor = Any


def _handle_segment_error(exc: SegmentAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _segment_connector_and_key(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "segment", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Segment connector found for org")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "segment", "segment", cid)
    try:
        write_key = resolve_segment_write_key(ctx.client, ctx.org_id, cid, ctx.settings)
    except SegmentAPIError as exc:
        raise _handle_segment_error(exc) from exc
    return cid, write_key


def _exec_segment_identify(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, write_key = _segment_connector_and_key(ctx, params)
    user_id = params.get("user_id") or params.get("userId")
    if not user_id:
        raise ToolValidationError("segment.identify requires user_id")
    traits = params.get("traits")
    try:
        data = identify(write_key, user_id=str(user_id), traits=traits if isinstance(traits, dict) else None)
    except SegmentAPIError as exc:
        raise _handle_segment_error(exc) from exc
    return NormalizedResult(success=True, action="segment.identify", connector_id=cid, data=data)


def _exec_segment_track(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, write_key = _segment_connector_and_key(ctx, params)
    event = params.get("event") or params.get("event_name") or params.get("eventName")
    if not event:
        raise ToolValidationError("segment.track requires event")
    properties = params.get("properties")
    context = params.get("context")
    try:
        data = track(
            write_key,
            user_id=params.get("user_id") or params.get("userId"),
            anonymous_id=params.get("anonymous_id") or params.get("anonymousId"),
            event=str(event),
            properties=properties if isinstance(properties, dict) else None,
            context=context if isinstance(context, dict) else None,
        )
    except SegmentAPIError as exc:
        raise _handle_segment_error(exc) from exc
    return NormalizedResult(success=True, action="segment.track", connector_id=cid, data=data)


def _exec_segment_group(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, write_key = _segment_connector_and_key(ctx, params)
    user_id = params.get("user_id") or params.get("userId")
    group_id = params.get("group_id") or params.get("groupId")
    if not user_id or not group_id:
        raise ToolValidationError("segment.group requires user_id and group_id")
    traits = params.get("traits")
    try:
        data = group(
            write_key,
            user_id=str(user_id),
            group_id=str(group_id),
            traits=traits if isinstance(traits, dict) else None,
        )
    except SegmentAPIError as exc:
        raise _handle_segment_error(exc) from exc
    return NormalizedResult(success=True, action="segment.group", connector_id=cid, data=data)


TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    "segment.identify": _exec_segment_identify,
    "segment.track": _exec_segment_track,
    "segment.group": _exec_segment_group,
}
