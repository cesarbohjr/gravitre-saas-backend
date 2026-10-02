"""MKT-AUDIT-13.2: Strategic hours saved ROI dashboard."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.marketplace.roi import marketplace_roi_summary


def test_marketplace_roi_summary_realizes_hours_with_usage():
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.execute.return_value = MagicMock(
        data=[
            {
                "id": "install-1",
                "asset_id": "asset-1",
                "installed_at": "2026-06-01T00:00:00Z",
                "marketplace_assets": {
                    "slug": "workflow-pack",
                    "title": "Workflow Pack",
                    "estimated_hours_saved": 5.0,
                    "business_outcome": "Faster ops",
                    "use_case": "Ops",
                },
            }
        ]
    )
    events = MagicMock()
    events.select.return_value = events
    events.eq.return_value = events
    events.execute.return_value = MagicMock(data=[{"asset_id": "asset-1"}, {"asset_id": "asset-1"}])

    client = MagicMock()

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_adoption_events":
            return events
        fallback = MagicMock()
        fallback.select.return_value = fallback
        fallback.eq.return_value = fallback
        fallback.execute.return_value = MagicMock(data=[], count=2)
        return fallback

    client.table.side_effect = table
    summary = marketplace_roi_summary(client, "org-1")
    assert summary["activeInstalls"] == 1
    assert summary["totalEstimatedHoursSaved"] == 5.0
    assert summary["totalRealizedHoursSaved"] == 5.0
    assert summary["byAsset"][0]["usageEvents"] == 2


def test_marketplace_roi_summary_zero_when_no_usage():
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.execute.return_value = MagicMock(
        data=[
            {
                "id": "install-1",
                "asset_id": "asset-1",
                "installed_at": "2026-06-01T00:00:00Z",
                "marketplace_assets": {
                    "slug": "agent-pack",
                    "title": "Agent Pack",
                    "estimated_hours_saved": 4.0,
                    "business_outcome": None,
                    "use_case": None,
                },
            }
        ]
    )
    events = MagicMock()
    events.select.return_value = events
    events.eq.return_value = events
    events.execute.return_value = MagicMock(data=[])

    client = MagicMock()

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_adoption_events":
            return events
        fallback = MagicMock()
        fallback.select.return_value = fallback
        fallback.eq.return_value = fallback
        fallback.execute.return_value = MagicMock(data=[], count=0)
        return fallback

    client.table.side_effect = table
    summary = marketplace_roi_summary(client, "org-1")
    assert summary["totalEstimatedHoursSaved"] == 4.0
    assert summary["totalRealizedHoursSaved"] == 0.0
    assert summary["realizationRate"] == 0.0
    assert summary["assetsWithUsage"] == 0


def test_marketplace_roi_summary_empty_installs():
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.execute.return_value = MagicMock(data=[])
    events = MagicMock()
    events.select.return_value = events
    events.eq.return_value = events
    events.execute.return_value = MagicMock(data=[])

    client = MagicMock()

    def table(name):
        if name == "marketplace_installs":
            return installs
        if name == "marketplace_asset_adoption_events":
            return events
        fallback = MagicMock()
        fallback.select.return_value = fallback
        fallback.eq.return_value = fallback
        fallback.execute.return_value = MagicMock(data=[], count=0)
        return fallback

    client.table.side_effect = table
    summary = marketplace_roi_summary(client, "org-1")
    assert summary["activeInstalls"] == 0
    assert summary["totalEstimatedHoursSaved"] == 0.0
    assert summary["realizationRate"] == 0.0
    assert summary["byAsset"] == []


def test_marketplace3_outcome_pack_requires_verified_play_outcome_for_realized_value():
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.execute.return_value = MagicMock(
        data=[
            {
                "id": "install-outcome",
                "asset_id": "asset-outcome",
                "installed_at": "2026-10-02T00:00:00Z",
                "installed_entity_type": "outcome_pack",
                "metadata": {
                    "plays": [
                        {"playKey": "sla-rescue"},
                        {"playKey": "knowledge-gap-miner"},
                    ]
                },
                "marketplace_assets": {
                    "slug": "msp-service-desk-3",
                    "title": "MSP Service Desk 3.0",
                    "estimated_hours_saved": 40.0,
                    "business_outcome": "Improve SLA performance",
                    "use_case": "MSP Service Desk",
                },
            }
        ]
    )
    adoption = MagicMock()
    adoption.select.return_value = adoption
    adoption.eq.return_value = adoption
    adoption.execute.return_value = MagicMock(data=[{"asset_id": "asset-outcome"}])

    outcomes = MagicMock()
    outcomes.select.return_value = outcomes
    outcomes.eq.return_value = outcomes
    outcomes.execute.return_value = MagicMock(data=[])

    client = MagicMock()
    client.table.side_effect = lambda name: (
        installs
        if name == "marketplace_installs"
        else adoption
        if name == "marketplace_asset_adoption_events"
        else outcomes
        if name == "intelligence_outcome_events"
        else MagicMock()
    )

    summary = marketplace_roi_summary(client, "org-1")

    row = summary["byAsset"][0]
    assert row["usageEvents"] == 1
    assert row["verifiedOutcomeEvents"] == 0
    assert row["measurementBasis"] == "verified_play_outcomes"
    assert row["realizedHoursSaved"] == 0.0


def test_marketplace3_outcome_pack_realizes_value_after_verified_play_business_result():
    installs = MagicMock()
    installs.select.return_value = installs
    installs.eq.return_value = installs
    installs.execute.return_value = MagicMock(
        data=[
            {
                "id": "install-outcome",
                "asset_id": "asset-outcome",
                "installed_at": "2026-10-02T00:00:00Z",
                "installed_entity_type": "outcome_pack",
                "metadata": {"plays": [{"playKey": "sla-rescue"}]},
                "marketplace_assets": {
                    "slug": "msp-service-desk-3",
                    "title": "MSP Service Desk 3.0",
                    "estimated_hours_saved": 40.0,
                    "business_outcome": "Improve SLA performance",
                    "use_case": "MSP Service Desk",
                },
            }
        ]
    )
    adoption = MagicMock()
    adoption.select.return_value = adoption
    adoption.eq.return_value = adoption
    adoption.execute.return_value = MagicMock(data=[{"asset_id": "asset-outcome"}])

    outcomes = MagicMock()
    outcomes.select.return_value = outcomes
    outcomes.eq.return_value = outcomes
    outcomes.execute.return_value = MagicMock(
        data=[
            {
                "id": "outcome-1",
                "measurement_status": "recorded",
                "metadata": {
                    "play_key": "sla-rescue",
                    "verification_state": "VERIFIED SUCCESS",
                    "verified": True,
                },
            }
        ]
    )

    client = MagicMock()
    client.table.side_effect = lambda name: (
        installs
        if name == "marketplace_installs"
        else adoption
        if name == "marketplace_asset_adoption_events"
        else outcomes
        if name == "intelligence_outcome_events"
        else MagicMock()
    )

    summary = marketplace_roi_summary(client, "org-1")

    row = summary["byAsset"][0]
    assert row["verifiedOutcomeEvents"] == 1
    assert row["realizedHoursSaved"] == 40.0
    assert summary["totalVerifiedOutcomeEvents"] == 1
