"""Item 4 — CRM outcome capture unit tests (no ML)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.crm_outcome_capture_service import (
    CRM_OUTCOME_TYPES,
    ingest_crm_recommendation_outcome,
)


def test_crm_outcome_types_are_product_labels():
    assert CRM_OUTCOME_TYPES == {"contacted", "replied", "booked", "won", "lost"}


def test_ingest_rejects_synthetic_unknown_type():
    with pytest.raises(ValueError, match="Invalid CRM outcome_type"):
        ingest_crm_recommendation_outcome(
            MagicMock(),
            org_id="org-1",
            outcome_type="made_up",
        )


def test_ingest_persists_row():
    table = MagicMock()
    table.insert.return_value = table
    table.execute.return_value = MagicMock(data=[{}])
    client = MagicMock()
    client.table.return_value = table

    result = ingest_crm_recommendation_outcome(
        client,
        org_id="org-1",
        outcome_type="contacted",
        connector_type="hubspot",
        external_record_id="deal-1",
        icp_score=0.82,
    )
    assert result["stored"] is True
    assert result["outcomeType"] == "contacted"
    client.table.assert_called_with("crm_recommendation_outcomes")
    payload = table.insert.call_args.args[0]
    assert payload["org_id"] == "org-1"
    assert payload["connector_type"] == "hubspot"
