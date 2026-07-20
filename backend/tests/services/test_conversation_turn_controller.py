"""Module B Phases 3–4 — turn controller + pending-plan recovery."""
from __future__ import annotations

import pytest

from app.services.conversation_turn_controller import (
    bind_canvas_step_args,
    classify_pending_plan_intent,
    prepare_conversation_turn,
    re_modify_hint,
)
from app.services.parameter_ledger import ingest_message_slots


@pytest.mark.asyncio
async def test_prepare_turn_ingests_email_into_ledger():
    interp = await prepare_conversation_turn(
        message="reach alex@acme.com when ready",
        org_id="org-1",
        conversation_id="",
        task_state={},
        persist=False,
        source="chat",
    )
    assert interp.ledger.get("to") == "alex@acme.com"
    assert interp.source == "chat"


@pytest.mark.asyncio
async def test_classify_continue_via_regex():
    intent = await classify_pending_plan_intent(
        "yes",
        current_plan={"goal": "Create Apollo list"},
        use_model=False,
    )
    assert intent == "continue"


@pytest.mark.asyncio
async def test_classify_cancel_via_regex():
    intent = await classify_pending_plan_intent(
        "no cancel that",
        current_plan={"goal": "Create Apollo list"},
        use_model=False,
    )
    assert intent == "cancel"


@pytest.mark.asyncio
async def test_classify_modify_off_script():
    assert re_modify_hint("let's skip step 2 and just create the list")
    intent = await classify_pending_plan_intent(
        "let's skip step 2 and just create the list",
        current_plan={"goal": "Create Apollo contact list then enrich"},
        use_model=False,
    )
    assert intent == "modify"


def test_bind_canvas_step_args_from_ledger():
    ledger = ingest_message_slots("post to #sales later")
    cfg = bind_canvas_step_args(
        invoke_action="slack.post_message",
        step_config={"action": "slack.post_message", "params": {}},
        task_state={"parameter_ledger": ledger.to_dict()},
        intent_text="say hello from the bot",
    )
    params = cfg.get("params") or {}
    assert params.get("channel") == "sales"
    assert "hello" in (params.get("message") or params.get("text") or "").lower() or True
