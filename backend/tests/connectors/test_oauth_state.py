from __future__ import annotations

import time

import pytest

from app.connectors.oauth_state import (
    new_oauth_state_jti,
    new_oauth_state_nonce,
    sign_oauth_state,
    verify_oauth_state,
)
from app.connectors.oauth_state_store import reset_oauth_state_store_for_tests


def _payload(**overrides):
    now = time.time()
    base = {
        "org_id": "o1",
        "user_id": "u1",
        "connector_id": "c1",
        "provider": "github",
        "iat": now,
        "exp": now + 300,
        "jti": new_oauth_state_jti(),
        "nonce": new_oauth_state_nonce(),
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _reset_jti_store():
    reset_oauth_state_store_for_tests()
    yield
    reset_oauth_state_store_for_tests()


def test_sign_and_verify_roundtrip():
    secret = "test-secret-key"
    token = sign_oauth_state(_payload(), secret)
    decoded = verify_oauth_state(token, secret, expected_provider="github")
    assert decoded["org_id"] == "o1"
    assert decoded["connector_id"] == "c1"


def test_verify_rejects_tampered_token():
    secret = "test-secret-key"
    token = sign_oauth_state(_payload(), secret)
    bad = token[:-2] + "xx"
    with pytest.raises(ValueError, match="signature"):
        verify_oauth_state(bad, secret, expected_provider="github")


def test_verify_rejects_expired_token():
    secret = "test-secret-key"
    now = time.time()
    token = sign_oauth_state(
        _payload(iat=now - 700, exp=now - 100),
        secret,
    )
    with pytest.raises(ValueError, match="expired"):
        verify_oauth_state(token, secret, expected_provider="github")


def test_verify_rejects_replay():
    secret = "test-secret-key"
    jti = new_oauth_state_jti()
    token = sign_oauth_state(_payload(jti=jti), secret)
    verify_oauth_state(token, secret, expected_provider="github")
    with pytest.raises(ValueError, match="already used"):
        verify_oauth_state(token, secret, expected_provider="github")


def test_verify_rejects_provider_mismatch():
    secret = "test-secret-key"
    token = sign_oauth_state(_payload(provider="github"), secret)
    with pytest.raises(ValueError, match="provider mismatch"):
        verify_oauth_state(token, secret, expected_provider="zendesk")
