"""Phase 2 cross-conversation memory stays OFF by default."""
from __future__ import annotations

from app.config import Settings
from app.services.cross_conversation_ledger_memory import (
    feature_enabled,
    promote_confirmed_ledger_slots,
    recall_slots_into_ledger,
)
from app.services.parameter_ledger import ParameterLedger


def test_feature_flag_defaults_off():
    assert feature_enabled(Settings()) is False


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
