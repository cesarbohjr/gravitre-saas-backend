"""Regression: confidence-propose must never return a local-part suffix.

Round-2 live failure proposed ``moduleb@acme.test`` instead of
``sarah.chen.moduleb@acme.test`` because a greedy name→email regex
backtracked into a dotted local-part after ``\\b``.
"""
from __future__ import annotations

from app.services.clarification_engine import ClarificationEngine
from app.services.parameter_ledger import (
    ParameterLedger,
    extract_complete_emails,
    ingest_message_slots,
)


def test_extract_complete_emails_rejects_local_part_suffix():
    text = "Sarah Chen is sarah.chen.moduleb@acme.test"
    emails = extract_complete_emails(text)
    assert emails == ["sarah.chen.moduleb@acme.test"]
    assert "moduleb@acme.test" not in emails


def test_promote_likely_entity_keeps_full_dotted_local_part():
    """Exact Round-2 corruption pattern."""
    engine = ClarificationEngine()
    ledger = ParameterLedger()
    # High-confidence slots stripped (as in the live harness) — only recent context.
    task_state = {
        "recent_user_messages": [
            "FYI for later — Sarah Chen is sarah.chen.moduleb@acme.test. "
            "She's the only Sarah on this account."
        ],
        "parameter_ledger": {"slots": {}, "pending_missing": []},
    }
    engine._promote_likely_entity_matches(
        "Send an email to Sarah via Gmail about the renewal.",
        ledger,
        task_state,
    )
    assert ledger.get("to") == "sarah.chen.moduleb@acme.test"
    assert ledger.get("email") == "sarah.chen.moduleb@acme.test"
    assert "moduleb@acme.test" != ledger.get("to")
    slot = ledger.slots.get("to")
    assert slot is not None
    assert slot.confidence == "medium"


def test_catalog_write_propose_uses_full_address_not_suffix():
    engine = ClarificationEngine()
    ledger = ingest_message_slots(
        "FYI — Sarah Chen is sarah.chen.moduleb@acme.test"
    )
    # Force medium path: clear high-confidence slots, keep value out of ledger.
    for key in ("to", "email"):
        ledger.slots.pop(key, None)
    task_state = {
        "parameter_ledger": ledger.to_dict(),
        "recent_user_messages": [
            "FYI — Sarah Chen is sarah.chen.moduleb@acme.test"
        ],
        "clarified_params": {},
    }
    trigger = engine._catalog_write_clarification(
        "Send an email to Sarah via Gmail about the renewal.",
        {},
        task_state=task_state,
    )
    assert trigger is not None
    missing = str((trigger.get("template_vars") or {}).get("missing_param") or "")
    assert "sarah.chen.moduleb@acme.test" in missing
    assert "moduleb@acme.test" not in missing.replace("sarah.chen.moduleb@acme.test", "")
    assert trigger.get("clarification_mode") == "propose_confirm"


def test_promote_does_not_guess_when_name_ambiguous():
    engine = ClarificationEngine()
    ledger = ParameterLedger()
    task_state = {
        "recent_user_messages": [
            "Sarah is sarah.a@acme.test and also talk to Sam at sam.b@acme.test"
        ],
        "parameter_ledger": {"slots": {}, "pending_missing": []},
    }
    engine._promote_likely_entity_matches(
        "Send an email to Sarah via Gmail.",
        ledger,
        task_state,
    )
    # Sarah uniquely matches sarah.a — that is fine. Use two Sarahs to block.
    ledger2 = ParameterLedger()
    task_state2 = {
        "recent_user_messages": [
            "Sarah A is sarah.a@acme.test and Sarah B is sarah.b@acme.test"
        ],
        "parameter_ledger": {"slots": {}, "pending_missing": []},
    }
    engine._promote_likely_entity_matches(
        "Send an email to Sarah via Gmail.",
        ledger2,
        task_state2,
    )
    assert ledger2.get("to") is None
