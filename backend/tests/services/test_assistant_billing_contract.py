"""Billing recovery evidence follows the same chat/voice attribution context."""
from unittest.mock import MagicMock

import pytest

from app.services.cost_attribution import (
    AssistantBillingContract, assistant_billing_contract, attribution, insert_model_call,
)


def _row():
    return {"org_id": "org-a", "task_type": "summarization", "model_name": "gpt-5.5",
            "input_tokens": 100, "output_tokens": 20}


def test_contract_persists_evidence_and_does_not_leak():
    client = MagicMock()
    with (assistant_billing_contract(AssistantBillingContract("org-a", 1000)),
          attribution(turn_id="assistant:turn-a")):
        insert_model_call(client, _row())
    saved = client.table.return_value.insert.call_args.args[0]
    assert saved["billing_credits"] > 0
    assert saved["billing_included"] == 1000
    assert saved["billing_environment"] == "production"
    insert_model_call(client, _row())
    assert "billing_credits" not in client.table.return_value.insert.call_args.args[0]


@pytest.mark.parametrize("billable,task_type", [(False, "summarization"), (True, "embedding")])
def test_local_cache_and_separately_billed_embeddings_are_not_recovered(billable, task_type):
    client = MagicMock()
    with (assistant_billing_contract(AssistantBillingContract("org-a", 1000)),
          attribution(turn_id="assistant:turn-a")):
        insert_model_call(client, {**_row(), "task_type": task_type}, billable=billable)
    assert "billing_credits" not in client.table.return_value.insert.call_args.args[0]


def test_foreign_org_and_missing_turn_refuse_contract():
    client = MagicMock()
    with assistant_billing_contract(AssistantBillingContract("org-b", 1000)):
        with pytest.raises(ValueError, match="org mismatch"):
            insert_model_call(client, _row())
    with assistant_billing_contract(AssistantBillingContract("org-a", 1000)):
        with pytest.raises(ValueError, match="turn mismatch"):
            insert_model_call(client, _row())
    client.table.assert_not_called()


def test_missing_migration_never_drops_recovery_evidence():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.side_effect = RuntimeError("PGRST204")
    with (assistant_billing_contract(AssistantBillingContract("org-a", 1000)),
          attribution(turn_id="assistant:turn-a")):
        with pytest.raises(RuntimeError, match="PGRST204"):
            insert_model_call(client, _row())
    assert client.table.return_value.insert.call_count == 1
