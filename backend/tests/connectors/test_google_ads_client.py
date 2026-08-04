"""Unit tests for Google Ads GAQL wrappers (no live network)."""
from __future__ import annotations

import pytest

from app.connectors.google_ads import (
    GoogleAdsAPIError,
    campaign_ui_url,
    get_campaign,
    list_campaigns,
    normalize_customer_id,
    performance_report,
    set_campaign_status,
    update_campaign_budget,
)


def test_normalize_customer_id_strips_dashes():
    assert normalize_customer_id("123-456-7890") == "1234567890"


def test_normalize_customer_id_rejects_injection():
    with pytest.raises(GoogleAdsAPIError):
        normalize_customer_id("123 DROP TABLE")


def test_campaign_ui_url():
    assert "campaignId=99" in campaign_ui_url(customer_id="1234567890", campaign_id="99")


def test_get_campaign_rejects_non_numeric_id():
    with pytest.raises(GoogleAdsAPIError, match="numeric"):
        get_campaign("token", "1234567890", "abc", developer_token="dev")


def test_list_campaigns_builds_fixed_query(monkeypatch):
    captured: dict[str, str] = {}

    def fake_search(access_token, customer_id, query, **kwargs):
        captured["query"] = query
        return [
            {
                "campaign": {
                    "id": "1",
                    "name": "Summer",
                    "status": "ENABLED",
                    "resourceName": "customers/1234567890/campaigns/1",
                },
                "campaignBudget": {
                    "amountMicros": "5000000",
                    "resourceName": "customers/1234567890/campaignBudgets/9",
                },
            }
        ]

    monkeypatch.setattr("app.connectors.google_ads._search", fake_search)
    rows = list_campaigns("token", "1234567890", developer_token="dev", limit=10)
    assert "FROM campaign" in captured["query"]
    assert "SELECT" in captured["query"]
    assert ";" not in captured["query"]
    assert rows[0]["id"] == "1"
    assert "result_url" in rows[0]


def test_create_search_campaign_sets_eu_political_declaration(monkeypatch):
    from app.connectors import google_ads as ads

    captured: dict = {}

    def fake_mutate(access_token, customer_id, operations, **kwargs):
        captured["operations"] = operations
        return {"results": [{"resourceName": "customers/1234567890/campaigns/9"}]}

    monkeypatch.setattr(ads, "_mutate_campaigns", fake_mutate)
    out = ads.create_search_campaign(
        "token",
        "1234567890",
        developer_token="dev",
        name="Test",
        budget_resource_name="customers/1234567890/campaignBudgets/1",
        status="PAUSED",
    )
    body = captured["operations"][0]["create"]
    assert body["containsEuPoliticalAdvertising"] == "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
    assert out["campaign_id"] == "9"


def test_search_omits_page_size(monkeypatch):
    """Ads API v25 rejects pageSize (PAGE_SIZE_NOT_SUPPORTED)."""
    from app.connectors import google_ads as ads

    captured: dict = {}

    class _Resp:
        status_code = 200
        text = "{}"

        def json(self):
            return {"results": []}

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            captured["json"] = json
            return _Resp()

    monkeypatch.setattr(ads.httpx, "Client", _Client)
    ads._search("token", "1234567890", "SELECT campaign.id FROM campaign", developer_token="dev")
    assert "pageSize" not in (captured.get("json") or {})


def test_performance_report_rejects_injected_campaign_id():
    with pytest.raises(GoogleAdsAPIError, match="numeric"):
        performance_report(
            "token",
            "1234567890",
            developer_token="dev",
            campaign_id="1 OR 1=1",
        )


def test_performance_report_safe_dates(monkeypatch):
    captured: dict[str, str] = {}

    def fake_search(access_token, customer_id, query, **kwargs):
        captured["query"] = query
        return []

    monkeypatch.setattr("app.connectors.google_ads._search", fake_search)
    out = performance_report(
        "token",
        "1234567890",
        developer_token="dev",
        start_date="7daysAgo",
        end_date="yesterday",
    )
    assert "BETWEEN" in captured["query"]
    assert "7daysAgo" not in captured["query"]
    assert out["rows"] == []
    assert "ads.google.com" in out["result_url"]


def test_set_campaign_status_pause(monkeypatch):
    captured: dict = {}

    def fake_mutate(access_token, customer_id, operations, **kwargs):
        captured["operations"] = operations
        return {"results": [{"resourceName": operations[0]["update"]["resourceName"]}]}

    monkeypatch.setattr("app.connectors.google_ads._mutate_campaigns", fake_mutate)
    result = set_campaign_status(
        "token",
        "1234567890",
        developer_token="dev",
        campaign_id="42",
        status="PAUSED",
    )
    assert result["status"] == "PAUSED"
    assert result["campaign_id"] == "42"
    assert captured["operations"][0]["update"]["status"] == "PAUSED"
    assert "result_url" in result


def test_update_campaign_budget(monkeypatch):
    monkeypatch.setattr(
        "app.connectors.google_ads.get_campaign",
        lambda *a, **k: {
            "id": "42",
            "name": "Summer",
            "budget_resource_name": "customers/1234567890/campaignBudgets/9",
            "result_url": "https://ads.google.com/aw/campaigns?ocid=1234567890&campaignId=42",
        },
    )

    def fake_mutate(access_token, customer_id, operations, **kwargs):
        return {"results": operations}

    monkeypatch.setattr("app.connectors.google_ads._mutate_campaign_budgets", fake_mutate)
    result = update_campaign_budget(
        "token",
        "1234567890",
        developer_token="dev",
        campaign_id="42",
        amount_micros=25_000_000,
    )
    assert result["amount_micros"] == 25_000_000
    assert result["campaign_id"] == "42"
    assert result["result_url"]
