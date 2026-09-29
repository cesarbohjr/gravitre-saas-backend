import pytest

from app.plays.outcomes import (
    AttributionType,
    BusinessResultStatus,
    PlayBusinessResult,
    SourceRecordRef,
)


def test_execution_or_actioned_state_is_not_verified_business_success():
    result = PlayBusinessResult(
        org_id="org-1",
        play_key="revenue-recovery",
        play_version="1",
        outcome_type="revenue_recovery",
        status=BusinessResultStatus.ACTIONED,
        metric_key="arr",
        baseline_value=100.0,
        result_value=120.0,
        unit="revenue",
        currency="USD",
        attribution_type=AttributionType.CORRELATIONAL,
    )
    row = result.to_storage_row()
    assert result.verified is False
    assert row["measured_at"] is None
    assert row["metadata"]["verified"] is False
    assert row["measurement_status"] == "actioned"


def test_verified_success_requires_source_of_record_and_method():
    with pytest.raises(ValueError, match="verification_method"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="revenue-recovery",
            play_version="1",
            outcome_type="revenue_recovery",
            status=BusinessResultStatus.VERIFIED_SUCCESS,
        ).to_storage_row()

    with pytest.raises(ValueError, match="source-of-record"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="revenue-recovery",
            play_version="1",
            outcome_type="revenue_recovery",
            status=BusinessResultStatus.VERIFIED_SUCCESS,
            verification_method="invoice_re_read",
        ).to_storage_row()


def test_verified_success_maps_to_existing_intelligence_outcome_store_shape():
    result = PlayBusinessResult(
        org_id="org-1",
        play_key="revenue-recovery",
        play_version="1",
        play_instance_id="play-run-1",
        outcome_type="recovered_revenue",
        status=BusinessResultStatus.VERIFIED_SUCCESS,
        metric_key="recovered_revenue",
        workflow_id="workflow-1",
        workflow_run_id="run-1",
        entity_type="invoice",
        entity_id="inv-42",
        baseline_value=0.0,
        result_value=2500.0,
        unit="revenue",
        currency="USD",
        confidence=1.0,
        attribution_type=AttributionType.DIRECT,
        attribution_weight=1.0,
        source_records=(
            SourceRecordRef(system="quickbooks", record_type="invoice", record_id="inv-42"),
        ),
        evidence_ids=("observation-1",),
        action_tools=("quickbooks.invoices.create",),
        verification_method="source_of_record_re_read",
        occurred_at="2026-09-29T09:30:00+00:00",
    )
    row = result.to_storage_row()
    assert row["outcome_event"] == "play_business_result"
    assert row["workflow_id"] == "workflow-1"
    assert row["workflow_run_id"] == "run-1"
    assert row["before_value"] == 0.0
    assert row["after_value"] == 2500.0
    assert row["measured_at"] == "2026-09-29T09:30:00+00:00"
    assert row["metadata"]["delta_value"] == 2500.0
    assert row["metadata"]["verification_state"] == "VERIFIED SUCCESS"
    assert row["metadata"]["source_records"][0]["system"] == "quickbooks"


def test_confidence_and_attribution_weight_are_bounded():
    with pytest.raises(ValueError, match="confidence"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="customer-rescue",
            play_version="1",
            outcome_type="retention",
            status=BusinessResultStatus.DETECTED,
            confidence=1.1,
        ).to_storage_row()

    with pytest.raises(ValueError, match="attribution_weight"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="customer-rescue",
            play_version="1",
            outcome_type="retention",
            status=BusinessResultStatus.DETECTED,
            attribution_weight=-0.1,
        ).to_storage_row()


def test_verified_success_cannot_be_generic_action_execution():
    with pytest.raises(ValueError, match="action execution"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="revenue-recovery",
            play_version="1",
            outcome_type="action_execution",
            status=BusinessResultStatus.VERIFIED_SUCCESS,
            metric_key="open_invoice_balance",
            baseline_value=100.0,
            result_value=0.0,
            verification_method="source_of_record_re_read",
            source_records=(
                SourceRecordRef(system="quickbooks", record_type="invoice", record_id="inv-1"),
            ),
        ).to_storage_row()


def test_verified_success_requires_metric_and_baseline_measurements():
    with pytest.raises(ValueError, match="metric_key"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="revenue-recovery",
            play_version="1",
            outcome_type="recovered_revenue",
            status=BusinessResultStatus.VERIFIED_SUCCESS,
            baseline_value=100.0,
            result_value=0.0,
            verification_method="source_of_record_re_read",
            source_records=(
                SourceRecordRef(system="quickbooks", record_type="invoice", record_id="inv-1"),
            ),
        ).to_storage_row()

    with pytest.raises(ValueError, match="baseline_value and result_value"):
        PlayBusinessResult(
            org_id="org-1",
            play_key="revenue-recovery",
            play_version="1",
            outcome_type="recovered_revenue",
            status=BusinessResultStatus.VERIFIED_SUCCESS,
            metric_key="open_invoice_balance",
            baseline_value=None,
            result_value=0.0,
            verification_method="source_of_record_re_read",
            source_records=(
                SourceRecordRef(system="quickbooks", record_type="invoice", record_id="inv-1"),
            ),
        ).to_storage_row()
