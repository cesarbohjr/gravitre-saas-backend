from __future__ import annotations

import hashlib
import hmac

from app.connectors.pagerduty_webhooks import (
    canonical_event_type,
    event_matches_trigger,
    flatten_inbound_payload,
    normalize_pagerduty_event,
    verify_pagerduty_webhook_signature,
)


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def test_canonical_event_aliases():
    assert canonical_event_type("incident.trigger") == "incident.triggered"
    assert canonical_event_type("incident.acknowledge") == "incident.acknowledged"


def test_verify_pagerduty_signature():
    body = b'{"event":{"event_type":"incident.triggered"}}'
    secret = "pd-secret"
    assert verify_pagerduty_webhook_signature(
        body=body,
        signature=_sign(body, secret),
        secret=secret,
    )


def test_normalize_v3_incident_event():
    out = normalize_pagerduty_event(
        {
            "event": {
                "event_type": "incident.triggered",
                "data": {
                    "incident": {
                        "id": "INC123",
                        "incident_number": 42,
                        "summary": "DB down",
                        "urgency": "high",
                        "status": "triggered",
                    }
                },
            }
        }
    )
    assert out["incident"]["id"] == "INC123"
    assert out["pagerduty_event"]["event"] == "incident.triggered"


def test_event_matches_trigger():
    trigger = {"event": "incident.triggered", "workflow_id": "wf-1", "active": True}
    assert event_matches_trigger(trigger, event_type="incident.triggered")
    assert not event_matches_trigger(trigger, event_type="incident.acknowledged")


def test_flatten_messages_payload():
    events = flatten_inbound_payload(
        {"messages": [{"event": "incident.trigger", "incident": {"id": "X"}}]}
    )
    assert len(events) == 1
