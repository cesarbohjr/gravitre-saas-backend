import pytest

from app.plays.customer_rescue import observe_customer_rescue


@pytest.mark.asyncio
async def test_customer_rescue_is_advisory_and_never_claims_retention(monkeypatch):
    async def fake_cards(*_args, **_kwargs):
        return {
            "recommendations": [
                {
                    "id": "churn-1",
                    "kind": "churn_risk_advisory",
                    "title": "Account 1: high churn risk",
                    "reason": "Review with a human.",
                    "evidence": {"customerId": "1", "riskScore": 0.8},
                }
            ],
            "gate": {"ready": True},
            "trained": True,
        }

    monkeypatch.setattr(
        "app.plays.customer_rescue.build_churn_advisory_cards",
        fake_cards,
    )
    payload = await observe_customer_rescue(
        "org-1",
        settings=object(),
        client=object(),
    )
    assert payload["actionTaken"] is False
    card = payload["signals"][0]
    assert card["advisoryOnly"] is True
    assert card["businessResult"]["verified"] is False
    assert card["businessResult"]["retainedRevenue"] is None
    assert card["businessResult"]["churnAvoided"] is None
