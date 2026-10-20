"""Signed webhook-to-entitlement integration, without external Stripe writes."""
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from app.routers.webhooks import stripe as webhook
from app.billing.entitlements import compute_app_access
from tests.billing.test_stripe_webhook_processing import _FakeClient, _settings

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
GRANT = "11111111-1111-4111-8111-111111111111"
ATTEMPT = "22222222-2222-4222-8222-222222222222"


def signed_request(event, secret="whsec_founder_test"):
    payload = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
    request = MagicMock()
    request.body = AsyncMock(return_value=payload)
    request.headers = {"stripe-signature": f"t={timestamp},v1={signature}"}
    return request


@pytest.mark.asyncio
async def test_signed_trial_activation_redemption_replay_conversion_and_cancel(monkeypatch):
    settings = _settings()
    settings.stripe_secret_key = "sk_test_unused"
    settings.stripe_webhook_secret = "whsec_founder_test"
    settings.commercial_offers_enabled = True
    client = _FakeClient()
    client._store["org_promotional_grants"] = [{
        "id": GRANT, "org_id": ORG, "status": "available", "checkout_attempt_id": ATTEMPT,
    }]
    monkeypatch.setattr(webhook, "shared_service_client", lambda *_args: client)
    trial_end = int(time.time()) + 30 * 86400
    event = {"id": "evt_trial", "object": "event", "type": "customer.subscription.updated", "data": {"object": {
        "id": "sub_trial", "customer": "cus_trial", "status": "trialing", "trial_end": trial_end,
        "metadata": {"org_id": ORG, "plan_code": "control", "offer_grant_id": GRANT, "offer_attempt_id": ATTEMPT},
    }}}
    assert await webhook.stripe_webhook(signed_request(event), settings) == {"received": True}
    row = client._store["org_billing"][0]
    assert row["billing_status"] == "trialing"
    assert compute_app_access(row["billing_status"], trial_ends_at=row["current_period_end"])["can_access_app"]
    assert client._store["org_promotional_grants"][0]["status"] == "redeemed"
    assert (await webhook.stripe_webhook(signed_request(event), settings))["status"] == "already_processed"
    assert len(client._store["stripe_webhook_events"]) == 1

    event["id"] = "evt_active"
    event["data"]["object"]["status"] = "active"
    assert await webhook.stripe_webhook(signed_request(event), settings) == {"received": True}
    assert client._store["org_billing"][0]["billing_status"] == "active"
    event["id"] = "evt_cancel"
    event["type"] = "customer.subscription.deleted"
    event["data"]["object"]["status"] = "canceled"
    await webhook.stripe_webhook(signed_request(event), settings)
    assert not compute_app_access(client._store["org_billing"][0]["billing_status"])["can_access_app"]


@pytest.mark.asyncio
async def test_invalid_signature_cannot_change_entitlements(monkeypatch):
    settings = _settings()
    settings.stripe_secret_key = "sk_test_unused"
    settings.stripe_webhook_secret = "whsec_founder_test"
    client_factory = MagicMock()
    monkeypatch.setattr(webhook, "shared_service_client", client_factory)
    with pytest.raises(HTTPException) as exc:
        await webhook.stripe_webhook(signed_request({"id": "evt_forged", "type": "customer.subscription.updated"}, secret="wrong"), settings)
    assert exc.value.status_code == 400
    client_factory.assert_not_called()
