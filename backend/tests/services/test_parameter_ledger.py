"""Module B Phase 1 — conversation-scoped parameter ledger."""
from __future__ import annotations

from app.services.chat_connector_models import ConnectorActionPlan
from app.services.parameter_ledger import (
    ParameterLedger,
    apply_ledger_to_plan,
    bind_args_from_ledger,
    classify_awaiting_params_intent,
    format_awaiting_params_meta_answer,
    get_ledger,
    ingest_message_slots,
    is_awaiting_params,
    ledger_patch,
    resume_awaiting_params,
    seal_unified_turn_plan_args,
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


def test_email_local_part_subject_does_not_steal_subject_slot():
    """subject.pollution@acme.test must not match \\bsubject free-text extract."""
    ledger = ingest_message_slots(
        "recipient subject.pollution@acme.test, subject Integration proof, "
        "body Hello from subject-pollution repro."
    )
    assert ledger.get("to") == "subject.pollution@acme.test"
    assert ledger.get("subject") == "Integration proof"
    assert "hello" in (ledger.get("body") or "").lower()


def test_subject_line_body_say_does_not_leak_instruction_framing():
    """Natural compound phrasing must not slice 'line,' / 'of the email say' into slots."""
    ledger = ingest_message_slots(
        "Send it to Stephanie, with the subject line, hello and "
        "body of the email say: I'm just testing this"
    )
    assert ledger.get("subject") == "hello"
    assert ledger.get("body") == "I'm just testing this"
    assert "line" not in (ledger.get("subject") or "").lower()
    assert "of the email" not in (ledger.get("body") or "").lower()
    assert "say:" not in (ledger.get("body") or "").lower()


def test_unified_turn_sealed_args_survive_corrupt_ledger_rebind():
    """LIVE proposal args must win over polluted user_message ledger slots on resume."""
    polluted = ParameterLedger()
    polluted.upsert("subject", "line, hello and", source="user_message")
    polluted.upsert("body", "of the email say: I'm just testing this", source="user_message")
    plan = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send email",
        args={
            "to": "stephaniekhan2002@gmail.com",
            "subject": "hello",
            "body": "I'm just testing this",
        },
    )
    sealed = seal_unified_turn_plan_args(plan, ledger=polluted)
    assert sealed.slots["subject"].source == "unified_turn_live"
    assert sealed.get("subject") == "hello"
    assert sealed.get("body") == "I'm just testing this"

    rebound = bind_args_from_ledger(
        "gmail.messages.send",
        {
            "to": "stephaniekhan2002@gmail.com",
            "subject": "hello",
            "body": "I'm just testing this",
        },
        sealed,
    )
    assert rebound.get("subject") == "hello"
    assert rebound.get("body") == "I'm just testing this"

    # Resume with only an email must not reintroduce framing residue.
    patch = stage_awaiting_params(
        ConnectorActionPlan(
            tool_name="gmail_messages_send",
            invoke_action="gmail.messages.send",
            integration="gmail",
            kind="write",
            label="Send email",
            args={"subject": "hello", "body": "I'm just testing this"},
        ),
        ("recipient",),
        ledger=sealed,
        seal_source="unified_turn_live",
    )
    resumed, _, resume_patch = resume_awaiting_params(
        "her email address is: stephaniekhan2002@gmail.com",
        {**patch},
    )
    assert resumed is not None
    args = (resume_patch.get("pending_task") or {}).get("params", {}).get("args") or {}
    assert args.get("subject") == "hello"
    assert args.get("body") == "I'm just testing this"
    assert args.get("to") == "stephaniekhan2002@gmail.com"


def test_stage_awaiting_params_cannot_demote_unified_turn_live_seal():
    """Production bug: staging same values as staged_plan demoted LIVE seal → regex overwrite."""
    from app.services.connector_action_workflows import missing_params_stage_patch

    plan = ConnectorActionPlan(
        tool_name="gmail_messages_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send email",
        args={
            "to": "",
            "subject": "hello",
            "body": "I'm just testing this",
        },
    )
    sealed = seal_unified_turn_plan_args(plan)
    assert sealed.slots["subject"].source == "unified_turn_live"

    # Default seal_source (classical) must not demote LIVE-locked slots.
    patch = stage_awaiting_params(plan, ("recipient",), ledger=sealed)
    ledger_after = get_ledger(patch)
    assert ledger_after.slots["subject"].source == "unified_turn_live"
    assert ledger_after.get("subject") == "hello"

    # LIVE path passes seal_source through missing_params_stage_patch.
    staged = missing_params_stage_patch(
        plan,
        "Send it with the subject line, hello and body of the email say: I'm just testing this",
        task_state={**ledger_patch(sealed)},
        seal_source="unified_turn_live",
    )
    assert staged is not None
    _, stage_patch = staged
    live_ledger = get_ledger(stage_patch)
    assert live_ledger.slots["subject"].source == "unified_turn_live"
    assert live_ledger.get("body") == "I'm just testing this"

    # Later compound-sentence re-ingest must not overwrite sealed values.
    rebound = ingest_message_slots(
        "Send it to Stephanie, with the subject line, corrupted and "
        "body of the email say: polluted body",
        ledger=live_ledger,
    )
    assert rebound.get("subject") == "hello"
    assert rebound.get("body") == "I'm just testing this"
    assert rebound.slots["subject"].source == "unified_turn_live"


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


def test_meta_clarify_about_recipient_is_not_slot_answer():
    """Pending-param clarifying questions must not re-fill or pollute free-text."""
    q = "do you need the email address or name?"
    assert classify_awaiting_params_intent(q, ["recipient"]) == "meta_clarify"
    plan = ConnectorActionPlan(
        tool_name="gmail_send",
        invoke_action="gmail.messages.send",
        integration="gmail",
        kind="write",
        label="Send Gmail message",
        args={"subject": "test"},
    )
    patch = stage_awaiting_params(plan, ("recipient",), ledger=ingest_message_slots("send mail"))
    _, ledger, resume_patch = resume_awaiting_params(q, {**patch})
    args = (resume_patch.get("pending_task") or {}).get("params", {}).get("args") or {}
    assert "email address or name" not in str(args.get("subject") or "").lower()
    assert "email address or name" not in str(args.get("body") or "").lower()
    assert ledger.get("subject") in {None, "test"} or "email address" not in (
        ledger.get("subject") or ""
    ).lower()
    answer = format_awaiting_params_meta_answer(["recipient"], action_label="Send Gmail message")
    assert "email address" in answer.lower()
    assert "still needed" in answer.lower()


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
