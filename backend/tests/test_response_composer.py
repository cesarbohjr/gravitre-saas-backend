"""Response Composer: envelope coerce, leak filter, model composition, no raw errors."""

from __future__ import annotations

import pytest

from app.services.response_composer import (
    CHIP_STATUS,
    adopt_model_delta,
    chip_status_text,
    compose_user_reply,
    emit_stream_error,
    looks_like_raw_backend,
)
from app.services.response_envelope import coerce_user_envelope
from app.services.tool_types import NormalizedResult, ToolPermissionDeniedError


TRACEBACK = (
    "Traceback (most recent call last):\n"
    '  File "backend/app/services/tool_service.py", line 99, in invoke_tool\n'
    "sqlalchemy.exc.OperationalError: SQLSTATE 57014 statement timeout\n"
)


async def _compose_fn(**kwargs):
    kind = kwargs.get("kind") or "error"
    return f"That didn't go through ({kind}). I can retry when you're ready."


def test_coerce_normalized_result_aliases_error_detail():
    result = NormalizedResult(
        success=False,
        action="hubspot.contacts.create",
        error_code="permission_denied",
        error_message="missing oauth scope crm.objects.contacts.write",
    )
    env = coerce_user_envelope(result)
    assert env["success"] is False
    assert env["error_code"] == "permission_denied"
    assert env["error_detail"] == result.error_message
    assert env["error"] == result.error_message
    assert env["data"] == {}


def test_coerce_bare_exception_and_bare_string():
    env_exc = coerce_user_envelope(ToolPermissionDeniedError("nope"), action="gmail.messages.send")
    assert env_exc["success"] is False
    assert env_exc["error_code"] == "permission_denied"
    assert env_exc["error_detail"]
    env_str = coerce_user_envelope("ok done")
    assert env_str["success"] is True
    assert env_str["data"]["text"] == "ok done"


def test_looks_like_raw_backend_catches_known_leak_class():
    assert looks_like_raw_backend(TRACEBACK) is True
    assert looks_like_raw_backend("permission_denied") is True
    assert looks_like_raw_backend("CognitiveTurnKernel pre-ACT complete") is True
    assert looks_like_raw_backend("Slack isn't connected. Connect it and I'll pick this up.") is False
    assert looks_like_raw_backend("I'd need assistant_connector_status to verify Clay.") is True
    assert looks_like_raw_backend("Call getConnectorStatus first.") is True


def test_adopt_model_delta_drops_leaky_chunks():
    assert adopt_model_delta(TRACEBACK) == ""
    assert "Slack" in adopt_model_delta("Slack isn't connected.")


def test_chip_status_never_includes_traceback():
    text = chip_status_text(
        {"success": False, "error_code": "permission_denied", "error": TRACEBACK}
    )
    assert text == CHIP_STATUS["permission_denied"]
    assert "Traceback" not in text
    assert "sqlalchemy" not in text


def test_emit_stream_error_never_forwards_raw_exception():
    event = emit_stream_error("request_failed", detail=TRACEBACK)
    assert event.sse_type == "error"
    assert "Traceback" not in str(event.payload)
    assert "sqlalchemy" not in str(event.payload)


@pytest.mark.asyncio
async def test_compose_tool_failure_never_surfaces_traceback():
    env = coerce_user_envelope(
        {"success": False, "error_code": "tool_error", "error": TRACEBACK}
    )
    text = await compose_user_reply(
        env,
        kind="error",
        draft=TRACEBACK,
        user_message="Create a HubSpot contact",
        org_id="org",
        compose_fn=_compose_fn,
        client=None,
    )
    assert "Traceback" not in text
    assert "sqlalchemy" not in text
    assert "SQLSTATE" not in text
    assert text.strip()


@pytest.mark.asyncio
async def test_compose_timeout_and_permission_are_natural_language():
    timeout = await compose_user_reply(
        {"success": False, "error_code": "connector_timeout", "error_detail": TRACEBACK},
        kind="timeout",
        user_message="List my campaigns",
        org_id="org",
        compose_fn=_compose_fn,
    )
    permission = await compose_user_reply(
        {"success": False, "error_code": "permission_denied", "error_detail": "oauth scope missing"},
        kind="permission",
        user_message="Delete all Google Ads campaigns",
        org_id="org",
        compose_fn=_compose_fn,
    )
    assert "Traceback" not in timeout
    assert "permission_denied" not in permission
    assert "timeout" in timeout.lower() or "didn't go through" in timeout.lower()
    assert "permission" in permission.lower() or "didn't go through" in permission.lower()


@pytest.mark.asyncio
async def test_compose_clarify_is_specific_not_generic_when_draft_names_the_choice():
    async def clarify_fn(**kwargs):
        return "SEO — are we talking organic rankings, a content calendar, or a specific site drop?"

    text = await compose_user_reply(
        {"success": True, "data": {"text": "help me improve our SEO"}},
        kind="clarify",
        draft="help me improve our SEO",
        user_message="help me improve our SEO",
        org_id="org",
        compose_fn=clarify_fn,
    )
    assert "organic" in text.lower() or "ranking" in text.lower() or "calendar" in text.lower()
    assert "how can I help you today" not in text.lower()


@pytest.mark.asyncio
async def test_llm_failure_uses_blocked_register_not_raw_error():
    async def boom(**kwargs):
        raise RuntimeError(TRACEBACK)

    text = await compose_user_reply(
        {"success": False, "error_code": "tool_error", "error_detail": TRACEBACK},
        kind="error",
        draft=TRACEBACK,
        user_message="do the thing",
        org_id="org",
        compose_fn=boom,
    )
    assert "Traceback" not in text
    assert "RuntimeError" not in text
    assert text.strip()


@pytest.mark.asyncio
async def test_progress_kind_keeps_honest_stage_draft():
    draft = "I'm not executing anything. I'll show the plan for your approval."
    text = await compose_user_reply(
        {"success": True, "data": {"stage": "ACT", "text": draft}},
        kind="progress",
        draft=draft,
        spoken=True,
        user_message="Show me the complete plan. Don't execute.",
        org_id="org",
        compose_fn=_compose_fn,
    )
    assert text == draft
    assert "Traceback" not in text
    assert "CognitiveTurnKernel" not in text


@pytest.mark.asyncio
async def test_progress_kind_falls_back_to_honest_draft_when_llm_fails():
    async def boom(**kwargs):
        raise RuntimeError("composer down")

    draft = "I'm loading memory and knowledge now."
    text = await compose_user_reply(
        {"success": True, "data": {"stage": "RETRIEVE", "text": draft}},
        kind="progress",
        draft=draft,
        spoken=True,
        user_message="check HubSpot",
        org_id="org",
        compose_fn=boom,
    )
    assert text == draft
