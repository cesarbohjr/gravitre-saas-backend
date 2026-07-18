"""Churn labeled-feature contract + advisory surface."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.ml.churn_feature_ingest import (
    CHURN_METRIC_NAME,
    build_churn_outcome_row,
    count_labeled_churn_examples,
    extract_churn_features,
    features_usable,
    list_churn_training_rows,
    resolve_churn_label,
    training_gate_status,
    upsert_churn_training_example,
)
from app.services.churn_advisory_service import _FORBIDDEN_ACTIONS, build_churn_advisory_cards


def test_extract_and_usable_features():
    feats = extract_churn_features(
        {"days_since_last_activity": 40, "open_support_tickets": 2, "noise": 9}
    )
    assert feats["days_since_last_activity"] == 40.0
    assert "noise" not in feats
    assert features_usable(feats) is True
    assert features_usable(extract_churn_features({})) is False


def test_resolve_churn_label():
    assert resolve_churn_label(churned=True) is True
    assert resolve_churn_label(label_reason="non_renew") is True
    assert resolve_churn_label(label_reason="renewed") is False
    assert resolve_churn_label() is None


def test_build_churn_outcome_row_contract():
    row = build_churn_outcome_row(
        org_id="org-1",
        customer_id="cust-1",
        features={"days_since_last_activity": 90, "open_support_tickets": 3},
        churned=True,
        label_reason="cancel",
    )
    assert row["metric_name"] == CHURN_METRIC_NAME
    assert row["target_entity_type"] == "customer"
    assert row["outcome_success"] is False
    assert row["outcome_payload"]["days_since_last_activity"] == 90.0
    assert row["outcome_payload"]["advisory_only"] is True


def test_build_rejects_all_zero_features():
    with pytest.raises(ValueError, match="positive"):
        build_churn_outcome_row(
            org_id="org-1",
            customer_id="cust-1",
            features={},
            churned=False,
        )


def _mock_churn_select(client: MagicMock, data: list[dict]) -> None:
    """Wire supabase-style chained select → eq → eq → not_.is_ → execute."""
    chain = client.table.return_value.select.return_value
    chain.eq.return_value = chain
    chain.not_.is_.return_value = chain
    chain.execute.return_value = MagicMock(data=data)


def test_list_and_count_labeled_rows():
    client = MagicMock()
    _mock_churn_select(
        client,
        [
            {
                "id": "1",
                "target_entity_id": "c1",
                "outcome_success": False,
                "outcome_payload": {"days_since_last_activity": 10, "open_support_tickets": 1},
            },
            {
                "id": "2",
                "target_entity_id": "c2",
                "outcome_success": True,
                "outcome_payload": {},
            },
        ],
    )
    rows = list_churn_training_rows(client, "org-1")
    assert len(rows) == 1
    assert rows[0]["churned"] is True
    assert count_labeled_churn_examples(client, "org-1") == 1
    gate = training_gate_status(client, "org-1")
    assert gate["current"] == 1
    assert gate["required"] == 30
    assert gate["ready"] is False


def test_upsert_calls_delete_then_insert():
    client = MagicMock()
    client.table.return_value.delete.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value = (
        MagicMock()
    )
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "new"}]
    )
    result = upsert_churn_training_example(
        client,
        org_id="org-1",
        customer_id="cust-9",
        features={"email_engagement_score": 0.2},
        label_reason="active",
    )
    assert result["ok"] is True
    assert result["churned"] is False
    assert client.table.return_value.insert.called


@pytest.mark.asyncio
async def test_advisory_cards_never_executable():
    client = MagicMock()
    _mock_churn_select(
        client,
        [
            {
                "id": "1",
                "target_entity_id": "acct-1",
                "outcome_success": False,
                "outcome_payload": {
                    "days_since_last_activity": 120,
                    "open_support_tickets": 5,
                    "failed_payments_30d": 1,
                },
            }
        ],
    )
    payload = await build_churn_advisory_cards("org-1", client=client, limit=5)
    assert payload["advisory_only"] is True
    assert payload["auto_contact"] is False
    assert "execute_plan" in _FORBIDDEN_ACTIONS
    for card in payload["recommendations"]:
        assert card.get("executable") is False
        assert card.get("advisory_only") is True
        assert "invoke" not in card
        assert "approval_token" not in card
