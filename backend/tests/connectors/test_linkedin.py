from __future__ import annotations

from unittest.mock import patch

from app.connectors.linkedin import build_stub_enrichment, enrich_prospect


def test_build_stub_enrichment_from_params():
    result = build_stub_enrichment(
        {
            "email": "alex@acme.com",
            "first_name": "Alex",
            "last_name": "Rivera",
            "company": "Acme",
            "title": "VP Sales",
        }
    )
    assert result["source"] == "manual_stub"
    assert result["enriched"] is False
    assert result["prospect"]["email"] == "alex@acme.com"
    assert result["prospect"]["fullName"] == "Alex Rivera"


def test_enrich_prospect_without_token_returns_stub():
    result = enrich_prospect(params={"email": "a@b.com", "company": "Beta"}, access_token=None)
    assert result["source"] == "manual_stub"


def test_enrich_prospect_with_token_uses_marketing_api():
    with patch(
        "app.connectors.linkedin._marketing_api_enrichment",
        return_value={
            "source": "linkedin_marketing_api",
            "enriched": True,
            "prospect": {"email": "a@b.com"},
            "confidence": 70,
        },
    ):
        result = enrich_prospect(params={"email": "a@b.com"}, access_token="token")
    assert result["source"] == "linkedin_marketing_api"
    assert result["enriched"] is True
