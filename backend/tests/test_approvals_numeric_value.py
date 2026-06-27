from __future__ import annotations

from unittest.mock import MagicMock

from app.services.approval_record_service import (
    create_contract_approval,
    extract_numeric_value,
    sync_workflow_pending_approval,
)
from app.services.memory_promotion_service import MemoryPromotionService


def test_numeric_value_nullable():
    numeric_value, currency, label = extract_numeric_value(
        context={"workflow_id": "wf-1"},
        parameters={"notes": "no amount here"},
    )
    assert numeric_value is None
    assert currency is None
    assert label is None


def test_invoice_approval_populates_numeric_value():
    numeric_value, currency, label = extract_numeric_value(
        parameters={"invoice_amount": 4200.50, "currency": "usd"},
    )
    assert numeric_value == 4200.50
    assert currency == "USD"
    assert label == "invoice_amount"

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "a-1"}])
    row = create_contract_approval(
        client,
        org_id="org-1",
        title="Approve invoice payment",
        approval_type="invoice",
        parameters={"invoice_amount": 4200.50, "currency": "USD"},
    )
    payload = client.table.return_value.insert.call_args.args[0]
    assert payload["numeric_value"] == 4200.50
    assert payload["numeric_value_label"] == "invoice_amount"
    assert row is not None


def test_generic_task_approval_leaves_numeric_value_null():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "a-2"}])
    sync_workflow_pending_approval(
        client,
        org_id="org-1",
        run_id="run-1",
        workflow_id="wf-1",
        workflow_name="Daily sync",
        requested_by="user-1",
        parameters={"region": "us-east"},
        required_approvals=1,
    )
    payload = client.table.return_value.insert.call_args.args[0]
    assert payload["numeric_value"] is None
    assert payload["numeric_value_label"] is None


def test_decision_pattern_detector_now_uses_numeric_value():
    service = MemoryPromotionService(settings=MagicMock())
    decisions = []
    for idx in range(16):
        decisions.append(
            {
                "type": "invoice",
                "priority": "medium",
                "status": "approved",
                "numeric_value": float(1000 + idx),
                "numeric_value_label": "invoice_amount",
            }
        )
    for idx in range(4):
        decisions.append(
            {
                "type": "invoice",
                "priority": "medium",
                "status": "rejected",
                "numeric_value": float(9000 + idx),
                "numeric_value_label": "invoice_amount",
            }
        )
    patterns = service._detect_threshold_patterns(decisions)
    numeric_patterns = [p for p in patterns if p["evidence"].get("field") == "numeric_value"]
    assert numeric_patterns
    assert numeric_patterns[0]["evidence"]["label"] == "invoice_amount"
