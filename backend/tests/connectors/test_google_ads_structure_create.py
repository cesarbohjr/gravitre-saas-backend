"""Unit tests for Google Ads Search structure create (mocked mutates)."""
from __future__ import annotations

from app.connectors.google_ads import create_search_campaign_structure


def test_create_search_campaign_structure_builds_campaigns(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        "app.connectors.google_ads.create_campaign_budget",
        lambda *a, **k: (
            calls.append("budget"),
            {
                "budget_resource_name": "customers/1234567890/campaignBudgets/1",
                "budget_id": "1",
                "amount_micros": k["amount_micros"],
            },
        )[1],
    )
    monkeypatch.setattr(
        "app.connectors.google_ads.create_search_campaign",
        lambda *a, **k: (
            calls.append("campaign"),
            {
                "campaign_id": "10",
                "campaign_resource_name": "customers/1234567890/campaigns/10",
                "name": k["name"],
                "status": "PAUSED",
                "bidding_strategy": k["bidding_strategy"],
                "result_url": "https://ads.google.com/",
            },
        )[1],
    )
    monkeypatch.setattr(
        "app.connectors.google_ads.create_ad_group",
        lambda *a, **k: (
            calls.append("ad_group"),
            {
                "ad_group_id": "20",
                "ad_group_resource_name": "customers/1234567890/adGroups/20",
                "name": k["name"],
            },
        )[1],
    )
    monkeypatch.setattr(
        "app.connectors.google_ads.create_ad_group_keywords",
        lambda *a, **k: (
            calls.append("keywords"),
            {"created": [{"resource_name": "rn"}], "failures": []},
        )[1],
    )
    monkeypatch.setattr(
        "app.connectors.google_ads.add_campaign_negative_keywords",
        lambda *a, **k: (calls.append("negatives"), {"count": len(k["keywords"])})[1],
    )
    monkeypatch.setattr(
        "app.connectors.google_ads.create_conversion_action",
        lambda *a, **k: (
            calls.append("conversion"),
            {"conversion_action_id": "9", "name": k["name"]},
        )[1],
    )

    out = create_search_campaign_structure(
        "token",
        "123-456-7890",
        developer_token="dev",
        daily_budget_total=100.0,
        campaigns=[
            {
                "name": "RevOps / Sales Ops",
                "budget_weight": 0.3,
                "bidding_strategy": "MAXIMIZE_CONVERSIONS",
                "ad_groups": [
                    {
                        "name": "Problem Aware",
                        "keywords": [
                            {"text": "sales ops automation tools", "match_type": "BROAD"},
                        ],
                    }
                ],
            }
        ],
        negative_keywords=["gravitee", "free"],
        conversion_actions=[{"name": "Free Trial Signup", "category": "SIGNUP", "value": 10}],
    )

    assert out["customer_id"] == "1234567890"
    assert len(out["campaigns"]) == 1
    assert out["campaigns"][0]["name"] == "RevOps / Sales Ops"
    assert out["campaigns"][0]["ad_groups"][0]["name"] == "Problem Aware"
    assert "budget" in calls and "campaign" in calls and "ad_group" in calls
    assert "keywords" in calls and "negatives" in calls and "conversion" in calls
