"""Module B Phase 1 — conversation-scoped parameter ledger."""
from __future__ import annotations

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.parameter_ledger import (
    apply_ledger_to_plan,
    bind_args_from_ledger,
    get_ledger,
    ingest_message_slots,
    is_awaiting_params,
    resume_awaiting_params,
    stage_awaiting_params,
)


def test_ingest_email_writes_to_and_email_slots():
    ledger = ingest_message_slots("My contact is alex@acme.com for later")
    assert ledger.get("to") == "alex@acme.com"
    assert ledger.get("email") == "alex@acme.com"


def test_ingest_slack_channel():
    ledger = ingest_message_slots("post something in the general channel")
    assert ledger.get("channel") == "general"


def test_bind_gmail_from_unprompted_ledger():
    ledger = ingest_message_slots("alex@acme.com is the right person")
    args = bind_args_from_ledger("gmail.messages.send", {}, ledger)
    assert args.get("to") == "alex@acme.com"


def test_stage_and_resume_gmail_recipient():
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={},
    )
    ledger = ingest_message_slots("send an email")
    patch = stage_awaiting_params(plan, ("recipient",), ledger=ledger)
    assert patch["pending_task"]["status"] == "awaiting_params"
    assert is_awaiting_params(patch)

    task_state = {
        **patch,
        "recent_user_messages": ["send an email"],
    }
    resumed, updated, _ = resume_awaiting_params("alex@acme.com", task_state)
    assert resumed is not None
    assert resumed.args.get("to") == "alex@acme.com"
    assert updated.get("to") == "alex@acme.com"


def test_stage_and_resume_slack_body_via_ledger():
    plan = ConnectorActionPlan(
        tool_name="slack_send_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Send Slack",
        args={"channel": "general"},
    )
    ledger = ingest_message_slots("send a message in slack general channel")
    patch = stage_awaiting_params(plan, ("message",), ledger=ledger)
    task_state = {**patch, "recent_user_messages": ["send a message in slack general channel"]}
    resumed, _, _ = resume_awaiting_params("Sure, say hi everyone at Gravitre", task_state)
    assert resumed is not None
    assert resumed.args.get("channel") == "general"
    assert "hi everyone" in (resumed.args.get("message") or "").lower()


def test_apply_ledger_to_plan_unprompted_email():
    ledger = ingest_message_slots("reach alex@acme.com tomorrow")
    task_state = {"parameter_ledger": ledger.to_dict()}
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={"subject": "Follow-up", "body": "Hello"},
    )
    bound = apply_ledger_to_plan(plan, task_state)
    assert bound.args.get("to") == "alex@acme.com"


def test_legacy_slack_channel_bridge():
    ledger = get_ledger({"clarified_params": {"slack_channel": "sales"}})
    assert ledger.get("channel") == "sales"
