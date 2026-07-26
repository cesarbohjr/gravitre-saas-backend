"""Phase 2 cross-conversation memory."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.services.cross_conversation_ledger_memory import (
    feature_enabled,
    promote_confirmed_ledger_slots,
    recall_slots_into_ledger,
)
from app.services.entity_resolution_store import ResolutionHit
from app.services.parameter_ledger import ParameterLedger


def test_feature_flag_defaults_on():
    assert feature_enabled(Settings()) is True


def test_promote_noop_when_disabled():
    ledger = ParameterLedger()
    ledger.upsert("to", "a@acme.test", source="test", confidence="high")
    n = promote_confirmed_ledger_slots(
        None,
        org_id="org",
        conversation_id="c1",
        task_state={"parameter_ledger": ledger.to_dict()},
        settings=Settings(cross_conversation_ledger_memory_enabled=False),
    )
    assert n == 0


def test_recall_noop_when_disabled():
    ledger = ParameterLedger()
    out = recall_slots_into_ledger(
        None,
        org_id="org",
        ledger=ledger,
        aliases=["Sarah"],
        settings=Settings(cross_conversation_ledger_memory_enabled=False),
    )
    assert out.get("to") is None


def test_recall_fills_email_from_fuzzy_resolution_when_enabled():
    ledger = ParameterLedger()
    client = MagicMock()
    hit = ResolutionHit(
        alias_normalized="sarah smith",
        entity_type="email_recipient",
        entity_id="sarah@acme.test",
        integration="email",
        source="parameter_ledger_confirmed",
        confidence=0.9,
    )
    with patch(
        "app.services.cross_conversation_ledger_memory.lookup_resolutions",
        return_value=[],
    ), patch(
        "app.services.cross_conversation_ledger_memory.lookup_fuzzy_resolutions",
        return_value=[hit],
    ):
        out = recall_slots_into_ledger(
            client,
            org_id="org",
            ledger=ledger,
            aliases=["Sarah"],
            settings=Settings(cross_conversation_ledger_memory_enabled=True),
        )
    assert out.get("to") == "sarah@acme.test"
    assert out.slots["to"].confidence == "medium"
