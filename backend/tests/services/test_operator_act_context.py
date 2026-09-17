from app.services.operator_act_context import (
    build_operator_act_context,
    classify_operator_intent,
    compact_ledger_slots,
)


def test_classify_vague_and_read_write() -> None:
    assert classify_operator_intent("help") == "vague"
    assert classify_operator_intent("fix it") == "vague"
    assert classify_operator_intent("list hubspot contacts") == "read"
    assert classify_operator_intent("send the email to sarah") == "write"


def test_operator_act_json_is_computable_and_gates_writes() -> None:
    ctx = build_operator_act_context(
        user_text="handle this",
        connected_integrations=["hubspot", "gmail"],
        task_state={
            "parameter_ledger": {
                "slots": {"to": {"value": "sarah@acme.com"}, "channel": {"value": "#ops"}},
                "pending_missing": [],
            }
        },
    )
    assert ctx.vague is True
    assert ctx.payload["policy"]["silent_writes"] is False
    assert ctx.payload["policy"]["writes_require_explicit_confirm"] is True
    assert "hubspot" in {row["vendor"] for row in ctx.connected}
    assert ctx.ledger_slots["to"] == "sarah@acme.com"
    assert "<operator_act_json>" in ctx.section
    assert "never execute a silent write" in ctx.section.lower()
    assert any(row["kind"] == "read" for row in ctx.reachable_actions) or ctx.reachable_actions == []


def test_sole_connected_crm_is_not_asked() -> None:
    ctx = build_operator_act_context(
        user_text="Show me the deals that need attention.",
        connected_integrations=["hubspot", "slack"],
    )
    assert ctx.payload["policy"]["do_not_ask_unconnected_vendors"] is True
    assert ctx.payload["sole_connected_domains"]["crm"] == ["hubspot"]
    assert "do not ask which crm" in ctx.section.lower()


def test_disconnected_has_no_reachable_vendor() -> None:
    ctx = build_operator_act_context(
        user_text="list deals",
        connected_integrations=[],
    )
    assert ctx.connected == []
    assert "none this turn" in ctx.section


def test_compact_ledger_slots() -> None:
    slots = compact_ledger_slots(
        {"parameter_ledger": {"slots": {"subject": {"value": "Hello"}}}}
    )
    assert slots == {"subject": "Hello"}
