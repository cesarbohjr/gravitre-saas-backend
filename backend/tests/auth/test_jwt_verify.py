from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.auth.jwt_verify import decode_supabase_jwt, jwks_url_for_settings
from app.config import Settings


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="legacy-hs256-secret",
        openai_api_key="sk-test",
        anthropic_api_key="sk-test",
        google_api_key="g",
    )


def test_jwks_url_derived_from_supabase_url():
    settings = _settings()
    assert (
        jwks_url_for_settings(settings)
        == "https://test.supabase.co/auth/v1/.well-known/jwks.json"
    )


def test_decode_hs256_legacy_secret():
    settings = _settings()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user-abc",
            "email": "u@example.com",
            "aud": "authenticated",
            "iss": "https://test.supabase.co/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    payload = decode_supabase_jwt(token, settings)
    assert payload["sub"] == "user-abc"
    assert payload["email"] == "u@example.com"


def test_decode_es256_via_jwks_client():
    settings = _settings()
    private_key = ec.generate_private_key(ec.SECP256R1())
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user-es256",
            "email": "es@example.com",
            "aud": "authenticated",
            "iss": "https://test.supabase.co/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": "test-kid"},
    )

    mock_signing_key = MagicMock()
    mock_signing_key.key = private_key.public_key()

    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key

    with patch("app.auth.jwt_verify._get_jwks_client", return_value=mock_client):
        payload = decode_supabase_jwt(token, settings)

    assert payload["sub"] == "user-es256"
    mock_client.get_signing_key_from_jwt.assert_called_once_with(token)


def test_decode_rejects_unknown_algorithm():
    settings = _settings()
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "user-x",
            "aud": "authenticated",
            "iss": "https://test.supabase.co/auth/v1",
            "iat": now,
            "exp": now + 3600,
        },
        settings.supabase_jwt_secret,
        algorithm="HS256",
    )
    parts = token.split(".")
    import base64
    import json

    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    header["alg"] = "none"
    bad_header = (
        base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    )
    bad_token = f"{bad_header}.{parts[1]}.{parts[2]}"

    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_supabase_jwt(bad_token, settings)
