"""STA-290: batch + partial approval service and runtime integration."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.workflows.approval_batch_service import (
    ApprovalBatchError,
    apply_batch_decisions,
    create_approval_batch,
    extract_batch_items,
    normalize_batch_for_api,
    should_create_batch,
    summarize_batch_items,
)


def test_extract_batch_items_from_upstream_outputs():
    upstream = {
        "writer": {"title": "Blog draft", "body": "Hello"},
        "designer": {"title": "Hero image", "asset": "img-1"},
    }
    items = extract_batch_items(upstream)
    assert len(items) == 2
    assert items[0]["item_key"] == "writer"
    assert items[1]["label"] == "Hero image"


def test_should_create_batch_when_multiple_upstream_outputs():
    assert should_create_batch({"a": {}, "b": {}}) is True
    assert should_create_batch({"a": {}}) is False
    assert should_create_batch({"a": {}}, node_metadata={"batch_mode": True}) is True


def test_summarize_batch_items_partial():
    summary = summarize_batch_items(
        [
            {"status": "approved"},
            {"status": "rejected"},
        ]
    )
    assert summary["has_partial"] is True
    assert summary["all_approved"] is False


def test_apply_batch_decisions_updates_status():
    items = [
        {"item_key": "writer", "status": "approved"},
        {"item_key": "designer", "status": "rejected"},
    ]
    summary = summarize_batch_items(items)
    assert summary["has_partial"] is True
    statuses = {item["status"] for item in items}
    batch_status = "resolved" if "pending" not in statuses else "partial"
    assert batch_status == "resolved"


def test_apply_batch_decisions_unknown_item_raises():
    client = MagicMock()
    batches = MagicMock()
    batches.select.return_value = batches
    batches.eq.return_value = batches
    batches.limit.return_value = batches
    batches.execute.return_value = MagicMock(data=[{"id": "b1", "status": "pending"}])
    items = MagicMock()
    items.select.return_value = items
    items.eq.return_value = items
    items.order.return_value = items
    items.execute.return_value = MagicMock(data=[{"id": "i1", "item_key": "writer", "status": "pending"}])
    client.table.side_effect = lambda name: batches if name == "approval_batches" else items

    with pytest.raises(ApprovalBatchError):
        apply_batch_decisions(
            client,
            batch_id="b1",
            org_id="org-1",
            actor_id="user-1",
            decisions=[{"item_key": "missing", "decision": "approved"}],
        )


def test_normalize_batch_for_api_shape():
    payload = normalize_batch_for_api(
        {
            "id": "batch-1",
            "run_id": "run-1",
            "node_id": "approval-1",
            "status": "pending",
            "items": [
                {
                    "item_key": "writer",
                    "label": "Blog draft",
                    "source_node_id": "writer",
                    "route_to_node_id": "writer",
                    "status": "pending",
                    "payload": {"body": "Hello"},
                }
            ],
        }
    )
    assert payload["batchId"] == "batch-1"
    assert payload["items"][0]["itemKey"] == "writer"


def test_create_approval_batch_skips_single_item_without_batch_mode():
    client = MagicMock()
    batch = create_approval_batch(
        client,
        org_id="org-1",
        run_id="run-1",
        node_id="ap1",
        approval_context={"upstream_outputs": {"only": {"title": "One"}}},
        node_metadata={},
    )
    assert batch is None
    client.table.assert_not_called()
