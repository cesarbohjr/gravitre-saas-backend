"""Fix 1 — clarification must read the live parameter ledger every turn."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.clarification_engine import ClarificationEngine
from app.services.parameter_ledger import ingest_message_slots, ledger_patch


@pytest.fixture
def engine():
    eng = ClarificationEngine()
    eng._polish_question = AsyncMock(return_value=None)
    return eng


@pytest.mark.asyncio
async def test_unprompted_email_in_ledger_does_not_reask_recipient(engine):
    ledger = ingest_message_slots(
        "Quick note: the right contact for renewals is renewals.moduleb@acme.test"
    )
    engine._state.get_task_state = AsyncMock(
        return_value={
            **ledger_patch(ledger),
            "clarified_params": {},
            "recent_user_messages": [
                "Quick note: the right contact for renewals is renewals.moduleb@acme.test",
                "Thanks.",
                "Got it.",
            ],
        }
    )
    result = await engine.should_clarify(
        {
            "request": "Send an email about the renewal via Gmail.",
            "requires_action": True,
            "intent": "connector_action",
            "classification_confidence": 0.9,
        },
        {"connected_integrations": ["gmail"]},
        [],
        conversation_id="c1",
        org_id="o1",
        understanding={"connector_dependencies": ["gmail"]},
    )
    # May ask for body, but must not treat recipient as missing.
    if result.get("should_clarify"):
        question = (result.get("question") or "").lower()
        reason = (result.get("reason") or "").lower()
        missing = str((result.get("template_vars") or {}).get("missing_param") or "").lower()
        assert "recipient" not in missing or "renewals.moduleb@acme.test" in missing
        assert "recipient" not in reason or "renewals.moduleb@acme.test" in (
            question + reason + missing
        )


@pytest.mark.asyncio
async def test_catalog_write_uses_live_ledger_not_clarified_snapshot(engine):
    ledger = ingest_message_slots("channel #ops")
    ledger.upsert("to", "ops@acme.test", source="user_message", confidence="high")
    # Stale clarified_params deliberately omit the email — live ledger must win.
    engine._state.get_task_state = AsyncMock(
        return_value={
            **ledger_patch(ledger),
            "clarified_params": {"intent": "email_send"},
            "recent_user_messages": ["ops@acme.test is the ops alias"],
        }
    )
    trigger = engine._catalog_write_clarification(
        "Send an email via Gmail about the outage",
        {"intent": "email_send"},
        task_state={
            **ledger_patch(ledger),
            "clarified_params": {"intent": "email_send"},
            "recent_user_messages": ["ops@acme.test is the ops alias"],
        },
    )
    if trigger is not None:
        missing = str((trigger.get("template_vars") or {}).get("missing_param") or "").lower()
        assert "ops@acme.test" in missing or "recipient" not in missing
