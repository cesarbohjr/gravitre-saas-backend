"""Twilio helper utilities for execution-layer callers."""
from __future__ import annotations

from app.connectors.twilio_api import fetch_twilio_account_sid


def resolve_twilio_account_sid_from_api_key(
    *,
    api_key_sid: str,
    api_key_secret: str,
) -> str:
    """Resolve Account SID (AC...) using Twilio API key credentials."""
    return fetch_twilio_account_sid(
        api_key_sid=str(api_key_sid or "").strip(),
        api_key_secret=str(api_key_secret or "").strip(),
    )
