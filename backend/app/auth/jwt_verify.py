"""Supabase JWT verification (legacy HS256 + asymmetric signing keys via JWKS)."""
from __future__ import annotations

from functools import lru_cache

import jwt
from jwt import PyJWKClient, PyJWTError

from app.config import Settings

ASYMMETRIC_ALGORITHMS = frozenset(
    {"ES256", "ES384", "ES512", "RS256", "RS384", "RS512", "PS256", "PS384", "PS512"}
)


@lru_cache(maxsize=4)
def _get_jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_keys=True)


def jwks_url_for_settings(settings: Settings) -> str:
    return f"{settings.supabase_url_stripped}/auth/v1/.well-known/jwks.json"


def decode_supabase_jwt(token: str, settings: Settings) -> dict:
    """Verify and decode a Supabase-issued access token."""
    header = jwt.get_unverified_header(token)
    alg = (header.get("alg") or "").strip()
    if not alg:
        raise jwt.InvalidTokenError("JWT missing alg header")

    decode_kwargs = {
        "audience": settings.jwt_audience,
        "issuer": settings.jwt_issuer,
        "leeway": settings.supabase_jwt_leeway_seconds,
    }

    if alg == "HS256":
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            **decode_kwargs,
        )

    if alg in ASYMMETRIC_ALGORITHMS:
        client = _get_jwks_client(jwks_url_for_settings(settings))
        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=[alg],
            **decode_kwargs,
        )

    raise jwt.InvalidAlgorithmError(f"Unsupported JWT algorithm: {alg}")


__all__ = ["decode_supabase_jwt", "jwks_url_for_settings", "PyJWTError"]
