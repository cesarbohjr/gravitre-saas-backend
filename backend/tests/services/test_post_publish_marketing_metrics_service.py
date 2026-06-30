"""Tests for post-publish marketing metrics wiring (STA-293 Mode A)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.post_publish_marketing_metrics_service import (
    MARKETING_PUBLISH_ACTIONS,
    METRIC_GA4_SESSIONS,
    OBSERVABLE_MARKETING_METRICS,
    _ga4_report_rows,
    encode_ga4_entity_id,
    maybe_record_post_publish_marketing_baseline,
)
from app.services.tool_types import NormalizedResult, ToolContext


def test_observable_marketing_metrics_include_required_connectors():
    connectors = {row["connector"] for row in OBSERVABLE_MARKETING_METRICS}
    assert "google_analytics" in connectors
    assert "linkedin" in connectors
    assert "canva" in connectors
    assert "hubspot_campaign" in connectors


def test_ga4_report_rows_parse_campaign_metrics():
    report = {
        "rows": [
            {
                "dimensionValues": [{"value": "spring_launch"}],
                "metricValues": [{"value": "120"}, {"value": "4"}],
            },
            {
                "dimensionValues": [{"value": "evergreen"}],
                "metricValues": [{"value": "80"}, {"value": "2"}],
            },
        ]
    }
    rows = _ga4_report_rows(report)
    assert rows[0]["campaign"] == "spring_launch"
    assert rows[0]["sessions"] == 120.0
    assert rows[0]["conversions"] == 4.0


def test_encode_ga4_entity_id():
    assert encode_ga4_entity_id("123", "spring_launch") == "123::spring_launch"


def test_maybe_record_skips_without_agent():
    ctx = ToolContext(
        settings=MagicMock(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id=None,
    )
    result = NormalizedResult(success=True, action="analytics.reports.run", data={"report": {}})
    with patch(
        "app.services.post_publish_marketing_metrics_service.get_supabase_client"
    ) as mock_client:
        maybe_record_post_publish_marketing_baseline(
            ctx,
            action="analytics.reports.run",
            params={},
            result=result,
        )
    mock_client.assert_not_called()


def test_maybe_record_ga4_campaign_baselines():
    ctx = ToolContext(
        settings=MagicMock(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        agent_id="agent-1",
        run_id="run-1",
    )
    result = NormalizedResult(
        success=True,
        action="analytics.reports.run",
        data={
            "property_id": "999",
            "report": {
                "rows": [
                    {
                        "dimensionValues": [{"value": "launch_q2"}],
                        "metricValues": [{"value": "50"}, {"value": "3"}],
                    }
                ]
            },
        },
    )
    client = MagicMock()
    with patch(
        "app.services.post_publish_marketing_metrics_service.get_supabase_client",
        return_value=client,
    ):
        maybe_record_post_publish_marketing_baseline(
            ctx,
            action="analytics.reports.run",
            params={},
            result=result,
        )
    assert client.table.return_value.insert.call_count == 3
    first_payload = client.table.return_value.insert.call_args_list[0].args[0]
    assert first_payload["target_entity_type"] == "marketing_campaign"
    assert first_payload["metric_name"] == METRIC_GA4_SESSIONS
    assert first_payload["metric_value_before"] == 50.0


@pytest.mark.asyncio
async def test_fetch_marketing_metric_value_ga4_sessions():
    from app.services.post_publish_marketing_metrics_service import fetch_marketing_metric_value

    report = {
        "rows": [
            {
                "dimensionValues": [{"value": "launch_q2"}],
                "metricValues": [{"value": "75"}, {"value": "5"}],
            }
        ]
    }
    with patch(
        "app.services.post_publish_marketing_metrics_service._ga4_token_and_property",
        return_value=("token", "999"),
    ):
        with patch(
            "app.connectors.google_analytics.run_ga4_report",
            return_value=report,
        ):
            value = await fetch_marketing_metric_value(
                "org-1",
                target_entity_type="marketing_campaign",
                target_entity_id=encode_ga4_entity_id("999", "launch_q2"),
                metric_name=METRIC_GA4_SESSIONS,
            )
    assert value == 75.0


def test_marketing_publish_actions_include_ga4_and_canva():
    assert "analytics.reports.run" in MARKETING_PUBLISH_ACTIONS
    assert "canva.exports.create" in MARKETING_PUBLISH_ACTIONS
