"""AI Visibility UI agent tool executors (allowlisted consumer-UI scrape — S2)."""
from __future__ import annotations

from typing import Any

from app.connectors.ai_visibility_ui_api import (
    AiVisibilityUiError,
    captures_export,
    mentions_check,
    prompts_batch,
    resolve_ai_visibility_ui_connector,
    surfaces_list,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: AiVisibilityUiError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str | None]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, api_key = resolve_ai_visibility_ui_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except AiVisibilityUiError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "ai_visibility_ui", "ai_visibility_ui", cid)
    return cid, api_key


def _exec_surfaces_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _api_key = _session(ctx, params)
    data = {"surfaces": surfaces_list(), "result_url": None}
    return NormalizedResult(
        success=True, action="ai_visibility_ui.surfaces.list", connector_id=cid, data=data
    )


def _exec_mentions_check(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _api_key = _session(ctx, params)
    brand = str(params.get("brand") or params.get("name") or "").strip()
    prompt = str(params.get("prompt") or params.get("query") or "").strip()
    surface = str(params.get("surface") or params.get("platform") or "").strip()
    approval_id = str(params.get("approval_id") or "").strip() or None
    if not brand:
        raise ToolValidationError("ai_visibility_ui.mentions.check requires brand")
    if not prompt:
        raise ToolValidationError("ai_visibility_ui.mentions.check requires prompt")
    if not surface:
        raise ToolValidationError("ai_visibility_ui.mentions.check requires surface")
    try:
        data = mentions_check(
            brand=brand,
            prompt=prompt,
            surface=surface,
            settings=ctx.settings,
            client=ctx.client,
            org_id=ctx.org_id,
            connector_id=cid,
            approval_id=approval_id,
        )
    except AiVisibilityUiError as exc:
        raise _handle_error(exc) from exc
    success = bool(data.get("ok"))
    return NormalizedResult(
        success=success,
        action="ai_visibility_ui.mentions.check",
        connector_id=cid,
        data=data,
        error_message=None if success else str(data.get("error") or "mention check incomplete"),
    )


def _exec_prompts_batch(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _api_key = _session(ctx, params)
    brand = str(params.get("brand") or params.get("name") or "").strip()
    prompts = params.get("prompts")
    if isinstance(prompts, str) and prompts.strip():
        prompts = [prompts.strip()]
    if not isinstance(prompts, list):
        prompts = []
    surfaces = params.get("surfaces")
    if isinstance(surfaces, str) and surfaces.strip():
        surfaces = [surfaces.strip()]
    if not isinstance(surfaces, list):
        surfaces = []
    approval_id = str(params.get("approval_id") or "").strip() or None
    if not brand:
        raise ToolValidationError("ai_visibility_ui.prompts.batch requires brand")
    try:
        data = prompts_batch(
            brand=brand,
            prompts=[str(p) for p in prompts],
            surfaces=[str(s) for s in surfaces],
            settings=ctx.settings,
            client=ctx.client,
            org_id=ctx.org_id,
            connector_id=cid,
            approval_id=approval_id,
        )
    except AiVisibilityUiError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="ai_visibility_ui.prompts.batch", connector_id=cid, data=data
    )


def _exec_captures_export(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, _api_key = _session(ctx, params)
    captures = params.get("captures")
    if captures is None:
        captures = params.get("results")
    if not isinstance(captures, list):
        captures = []
    try:
        data = captures_export(captures=captures)
    except AiVisibilityUiError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="ai_visibility_ui.captures.export", connector_id=cid, data=data
    )


AI_VISIBILITY_UI_TOOL_EXECUTORS: dict[str, Any] = {
    "ai_visibility_ui.surfaces.list": _exec_surfaces_list,
    "ai_visibility_ui.mentions.check": _exec_mentions_check,
    "ai_visibility_ui.prompts.batch": _exec_prompts_batch,
    "ai_visibility_ui.captures.export": _exec_captures_export,
}
