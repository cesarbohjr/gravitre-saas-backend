"""Marketplace 3.0 ROI: adoption is not business-outcome proof."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.marketplace.roi import marketplace_roi_summary


def _install_row() -> dict:
    return {
        "id": "install-1",
        "asset_id": "asset-1",
        "installed_entity_type": "outcome_pack",
        "installed_at": "2026-06-01T00:00:00Z",
        "metadata": {
            "plays": [
                {"playKey": "sla-rescue"},
                {"playKey": "stale-ticket-recovery"},
            ]
        },
        "marketplace_assets": {
            "slug": "msp-service-desk-3",
            "title": "MSP Service Desk 3.0",
            "asset_type": "outcome_pack",
            "estimated_hours_saved": 5.0,
            "business_outcome": "Faster service desk operations",
            "use_case": "MSP Service Desk",
        },
    }


def _client(*, usage: list[dict] | None = None, outcomes: list[dict] | None = None, installs_data: list[dict] | None = None):
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.execute.return_value = MagicMock(data=installs_data if installs_data is not None else [_install_row()])

    adoption = MagicMock()
    adoption.select.return_value = adoption
    adoption.eq.return_value = adoption
    adoption.execute.return_value = MagicMock(data=usage or [], count=len(usage or []))

    outcome_table = MagicMock()
    outcome_table.select.return_value = outcome_table
    outcome_table.eq.return_value = outcome_table
    outcome_table.execute.return_value = MagicMock(data=outcomes or [])

    client = MagicMock()

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_adoption_events":
            return adoption
        if name == "intelligence_outcome_events":
            return outcome_table
        fallback = MagicMock()
        fallback.select.return_value = fallback
        fallback.eq.return_value = fallback
        fallback.execute.return_value = MagicMock(data=[], count=0)
        return fallback

    client.table.side_effect = table
    return client


def test_marketplace_roi_usage_does_not_realize_estimated_hours() -> None:
    summary = marketplace_roi_summary(
        _client(usage=[{"asset_id": "asset-1"}, {"asset_id": "asset-1"}]),
        "org-1",
    )
    assert summary["activeInstalls"] == 1
    assert summary["assetsWithUsage"] == 1
    assert summary["totalEstimatedHoursSaved"] == 5.0
    assert summary["totalRealizedHoursSaved"] == 0.0
    assert summary["byAsset"][0]["usageEvents"] == 2
    assert summary["byAsset"][0]["verifiedOutcomeEvents"] == 0
    assert summary["byAsset"][0]["outcomeVerified"] is False


def test_marketplace_roi_realizes_only_verified_measured_hours() -> None:
    outcomes = [
        {
            "id": "outcome-1",
            "entity_id": "sla-rescue",
            "before_value": 0,
            "after_value": 2.5,
            "measurement_status": "recorded",
            "metadata": {
                "play_key": "sla-rescue",
                "verification_state": "VERIFIED SUCCESS",
                "verified": True,
                "metric_key": "hours_saved",
                "unit": "hours",
                "delta_value": 2.5,
            },
        },
        {
            "id": "outcome-2",
            "entity_id": "stale-ticket-recovery",
            "before_value": 0,
            "after_value": 1.0,
            "measurement_status": "recorded",
            "metadata": {
                "play_key": "stale-ticket-recovery",
                "verification_state": "VERIFIED SUCCESS",
                "verified": True,
                "metric_key": "hours_saved",
                "unit": "hours",
                "delta_value": 1.0,
            },
        },
    ]
    summary = marketplace_roi_summary(_client(outcomes=outcomes), "org-1")
    assert summary["assetsWithVerifiedOutcomes"] == 1
    assert summary["totalVerifiedOutcomeEvents"] == 2
    assert summary["totalRealizedHoursSaved"] == 3.5
    assert summary["realizationRate"] == 70.0
    assert summary["byAsset"][0]["outcomeVerified"] is True


def test_verified_non_hour_outcome_proves_outcome_but_not_hours_saved() -> None:
    outcomes = [
        {
            "id": "outcome-1",
            "before_value": 72,
            "after_value": 91,
            "measurement_status": "recorded",
            "metadata": {
                "play_key": "sla-rescue",
                "verification_state": "VERIFIED SUCCESS",
                "verified": True,
                "metric_key": "sla_compliance",
                "unit": "percent",
                "delta_value": 19,
            },
        }
    ]
    summary = marketplace_roi_summary(_client(outcomes=outcomes), "org-1")
    assert summary["totalVerifiedOutcomeEvents"] == 1
    assert summary["totalRealizedHoursSaved"] == 0.0
    assert summary["byAsset"][0]["outcomeVerified"] is True


def test_marketplace_roi_summary_empty_installs() -> None:
    summary = marketplace_roi_summary(_client(installs_data=[]), "org-1")
    assert summary["activeInstalls"] == 0
    assert summary["totalEstimatedHoursSaved"] == 0.0
    assert summary["totalRealizedHoursSaved"] == 0.0
    assert summary["totalVerifiedOutcomeEvents"] == 0
    assert summary["byAsset"] == []
