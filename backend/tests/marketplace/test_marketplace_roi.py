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


def test_verified_outcomes_bind_to_current_install_and_do_not_measure_catalog_hours():
    from copy import deepcopy
    install = {"id": "install", "asset_id": "asset", "installed_at": "2026-10-20T00:00:00Z",
               "metadata": {"plays": [{"workflowId": "workflow"}]},
               "marketplace_assets": {"title": "Pack", "estimated_hours_saved": 5}}
    proof = {"id": "result", "org_id": "org", "workflow_id": "workflow", "workflow_run_id": "run",
             "created_at": "2026-10-21T00:00:00Z", "measurement_status": "recorded",
             "before_value": 2, "after_value": 3,
             "metadata": {"contract": "play_business_result/v1", "verified": True,
                          "verification_state": "VERIFIED SUCCESS", "verification_method": "entity_get",
                          "source_records": [{"record_id": "contact"}], "evidence_ids": ["evidence"],
                          "metric_key": "contacts", "outcome_type": "created"}}
    foreign = deepcopy(proof); foreign["org_id"] = "foreign"
    old = deepcopy(proof); old["created_at"] = "2026-10-19T00:00:00Z"
    unverified = deepcopy(proof); unverified["metadata"]["verified"] = False
    client = MagicMock()
    def table(name):
        query = MagicMock()
        for method in ("select", "eq", "limit"):
            getattr(query, method).return_value = query
        query.execute.return_value = MagicMock(data={
            "marketplace_installs": [install], "intelligence_outcome_events": [proof, proof, foreign, old, unverified],
        }.get(name, []), count=0)
        return query
    client.table.side_effect = table
    summary = marketplace_roi_summary(client, "org")
    assert summary["totalVerifiedOutcomeEvents"] == 1
    assert summary["totalRealizedHoursSaved"] == 0
    assert summary["valueBasis"] == "estimate"
