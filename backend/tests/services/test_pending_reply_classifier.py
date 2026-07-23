"""Module B — shared 7-way pending-reply classifier."""
from __future__ import annotations

import pytest

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.parameter_ledger import stage_awaiting_params
from app.services.pending_reply_classifier import (
    build_pending_snapshot,
    classify_pending_reply,
    classify_pending_reply_fast,
    format_ambiguous_clarify,
    format_pending_meta_answer,
    format_unrelated_hold_prompt,
    has_pending_family,
)


def _gmail_awaiting_params_state() -> dict:
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail message",
        args={"subject": "test"},
    )
    return stage_awaiting_params(plan, ("recipient",))


def test_has_pending_family_awaiting_params():
    state = _gmail_awaiting_params_state()
    assert has_pending_family(state) is True
    assert has_pending_family({}) is False


def test_fast_path_seven_intents_gmail_params():
    state = _gmail_awaiting_params_state()
    snap = build_pending_snapshot(state)
    assert classify_pending_reply_fast("alex@acme.com", snap) == "slot_answer"
    assert (
        classify_pending_reply_fast("do you need the email address or name?", snap)
        == "meta_clarify"
    )
    assert classify_pending_reply_fast("what format?", snap) in {
        "meta_clarify",
        "unrelated",
        "ambiguous",
    }
    assert classify_pending_reply_fast("cancel that", snap) == "reject"
    assert classify_pending_reply_fast("yes", snap) == "ambiguous"  # missing fields
    assert (
        classify_pending_reply_fast("What workflows have been ran?", snap) == "unrelated"
    )
    assert (
        classify_pending_reply_fast("what connectors are Connected right now?", snap)
        == "unrelated"
    )
    assert (
        classify_pending_reply_fast("actually make the subject Q3 instead", snap)
        == "modify"
    )


@pytest.mark.asyncio
async def test_classify_meta_and_unrelated_no_model():
    state = _gmail_awaiting_params_state()
    assert (
        await classify_pending_reply(
            "do you need the email address or name?",
            task_state=state,
            use_model=False,
        )
        == "meta_clarify"
    )
    assert (
        await classify_pending_reply(
            "What workflows have been ran?",
            task_state=state,
            use_model=False,
        )
        == "unrelated"
    )


def test_meta_answer_not_verbatim_still_needed_only():
    state = _gmail_awaiting_params_state()
    snap = build_pending_snapshot(state)
    answer = format_pending_meta_answer(snap)
    assert "email address" in answer.lower()
    assert "Here's where things stand" not in answer


def test_unrelated_hold_prompt_names_pending():
    state = _gmail_awaiting_params_state()
    snap = build_pending_snapshot(state)
    msg = format_unrelated_hold_prompt(snap, new_request="What workflows have been ran?")
    assert "abandon" in msg.lower()
    assert "hold" in msg.lower()
    assert "Send Gmail" in msg or "gmail" in msg.lower()


def test_ambiguous_asks_not_guesses():
    state = _gmail_awaiting_params_state()
    snap = build_pending_snapshot(state)
    msg = format_ambiguous_clarify(snap)
    assert "still needed" in msg.lower() or "not sure" in msg.lower()
    assert "0 recent runs" not in msg.lower()


def test_orch_plan_confirm_snapshot():
    state = {
        "pending_task": {
            "type": "connector_orchestration",
            "status": "awaiting_plan_confirm",
            "params": {"label": "Multi-step HubSpot"},
        },
        "current_plan": {"goal": "Enrich then create HubSpot deal"},
    }
    snap = build_pending_snapshot(state)
    assert has_pending_family(state)
    assert classify_pending_reply_fast("yes", snap) == "confirm"
    assert classify_pending_reply_fast("cancel", snap) == "reject"
    assert (
        classify_pending_reply_fast("why do you need approval?", snap)
        in {"meta_clarify", "unrelated", "ambiguous"}
    )


def test_other_connector_imperative_is_unrelated():
    state = _gmail_awaiting_params_state()
    snap = build_pending_snapshot(state)
    assert (
        classify_pending_reply_fast("search HubSpot for Acme contacts", snap)
        == "unrelated"
    )


def test_known_bug_phrasings_classified():
    """The three known bugs must land in the expanded ontology."""
    gmail = _gmail_awaiting_params_state()
    snap = build_pending_snapshot(gmail)
    assert (
        classify_pending_reply_fast("do you need the email address or name?", snap)
        == "meta_clarify"
    )

    # Sticky plan without awaiting_* (stale-plan family).
    plan_only = {"current_plan": {"goal": "Create HubSpot deal"}, "pending_task": None}
    snap2 = build_pending_snapshot(plan_only)
    assert has_pending_family(plan_only)
    assert (
        classify_pending_reply_fast("What workflows have been ran?", snap2)
        == "unrelated"
    )
