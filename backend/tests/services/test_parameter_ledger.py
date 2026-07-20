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


def test_resume_advances_pending_task_args_from_live_ledger():
    """Fix 1 — resume must rewrite pending_task.args, not leave a stale snapshot."""
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={"subject": "Follow-up"},
    )
    ledger = ingest_message_slots("Send an email via Gmail")
    patch = stage_awaiting_params(plan, ("recipient", "body"), ledger=ledger)
    assert (patch["pending_task"]["params"].get("args") or {}).get("to") is None

    task_state = {**patch, "recent_user_messages": ["Send an email via Gmail"]}
    resumed, _, resume_patch = resume_awaiting_params(
        "alex.moduleb.audit@acme.test — subject Module B cert, body Hello from live audit.",
        task_state,
    )
    assert resumed is not None
    assert resumed.args.get("to") == "alex.moduleb.audit@acme.test"
    advanced_args = (resume_patch.get("pending_task") or {}).get("params", {}).get("args") or {}
    assert advanced_args.get("to") == "alex.moduleb.audit@acme.test"
    assert "hello" in (advanced_args.get("body") or "").lower()


def test_ingest_title_is_unquoted():
    ledger = ingest_message_slots(
        "title is Checkout fails on mobile for VIP accounts priority urgent"
    )
    assert "checkout" in (ledger.get("title") or "").lower()


def test_filler_turn_does_not_pollute_subject():
    """Phase 0.1 — side questions must not fill free-text subject via resume."""
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={},
    )
    patch = stage_awaiting_params(plan, ("recipient", "subject", "body"))
    task_state = {**patch, "recent_user_messages": ["Send an email via Gmail"]}
    _, ledger, resume_patch = resume_awaiting_params(
        "Quick side note: what connectors are Connected in this org right now?",
        task_state,
    )
    assert ledger.get("subject") is None
    args = (resume_patch.get("pending_task") or {}).get("params", {}).get("args") or {}
    assert not str(args.get("subject") or "").strip() or "quick side" not in str(
        args.get("subject") or ""
    ).lower()


def test_explicit_subject_repairs_resume_pollution():
    """Write-protect + bind preference: user_message subject beats resume dump in args."""
    from app.services.parameter_ledger import ParameterLedger, bind_args_from_ledger

    ledger = ParameterLedger()
    ledger.upsert(
        "subject",
        "Quick side note: what connectors are Connected?",
        source="awaiting_params_resume",
    )
    ledger.upsert("subject", "Integration proof", source="user_message")
    assert ledger.get("subject") == "Integration proof"
    args = bind_args_from_ledger(
        "gmail.messages.send",
        {"subject": "Quick side note: what connectors are Connected?"},
        ledger,
    )
    assert args.get("subject") == "Integration proof"


def test_resume_pollution_then_explicit_fill_live_path():
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail",
        args={},
    )
    patch = stage_awaiting_params(plan, ("recipient", "subject", "body"))
    task_state = {**patch, "recent_user_messages": ["Send an email via Gmail"]}
    # If an older build polluted subject, explicit fill must repair it.
    polluted = dict(task_state)
    polluted["parameter_ledger"] = {
        "slots": {
            "subject": {
                "value": "Quick side note: what connectors are Connected in this org right now?",
                "source": "awaiting_params_resume",
                "confidence": "high",
            }
        },
        "pending_missing": ["recipient", "subject", "body"],
    }
    polluted["pending_task"]["params"]["args"] = {
        "subject": "Quick side note: what connectors are Connected in this org right now?"
    }
    resumed, ledger, resume_patch = resume_awaiting_params(
        "recipient integration.proof@acme.test, subject Integration proof, "
        "body Hello from the continuous 0-A-B-C-D trace.",
        polluted,
    )
    assert resumed is not None
    assert ledger.get("subject") == "Integration proof"
    args = (resume_patch.get("pending_task") or {}).get("params", {}).get("args") or {}
    assert args.get("subject") == "Integration proof"
    assert "quick side" not in (args.get("subject") or "").lower()
