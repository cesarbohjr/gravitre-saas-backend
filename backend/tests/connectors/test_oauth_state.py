from __future__ import annotations

import time

import pytest

from app.connectors.oauth_state import sign_oauth_state, verify_oauth_state


def test_sign_and_verify_roundtrip():
    secret = "test-secret-key"
    now = time.time()
    payload = {"org_id": "o1", "connector_id": "c1", "iat": now, "exp": now + 300}
    token = sign_oauth_state(payload, secret)
    decoded = verify_oauth_state(token, secret)
    assert decoded["org_id"] == "o1"
    assert decoded["connector_id"] == "c1"


def test_verify_rejects_tampered_token():
    secret = "test-secret-key"
    now = time.time()
    token = sign_oauth_state({"exp": now + 300}, secret)
    bad = token[:-2] + "xx"
    with pytest.raises(ValueError, match="signature"):
        verify_oauth_state(bad, secret)


def test_verify_rejects_expired_token():
    secret = "test-secret-key"
    now = time.time()
    token = sign_oauth_state({"iat": now - 700, "exp": now - 100}, secret)
    with pytest.raises(ValueError, match="expired"):
        verify_oauth_state(token, secret)
