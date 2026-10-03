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
