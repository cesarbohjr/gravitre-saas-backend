"""Plays production acceptance authenticates without a stored long-lived credential."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import jwt
import pytest

from app.services.conversation_write_guard import (
    FORBIDDEN_OPERATOR_ORG_ID,
    ConversationWriteBlockedError,
)

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "verify_plays_production", REPO / "scripts" / "verify-plays-production.py"
)
vpp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vpp)

SECRET = "plays-acceptance-test-secret-at-least-32-bytes"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in (
        "PLATFORM_LIVE_BEARER_TOKEN",
        "PLATFORM_LIVE_ORG_ID",
        "PLAYS_ACCEPTANCE_AUTH",
        "ISOLATED_CONVERSATION_TEST_ORG_ID",
        "ISOLATED_CONVERSATION_TEST_USER_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", SECRET)


def test_smoke_org_token_is_short_lived_and_scoped_to_the_smoke_actor(monkeypatch):
    monkeypatch.setenv("PLAYS_ACCEPTANCE_AUTH", "smoke-org")
    token, org_id, mode = vpp.session()
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], audience="authenticated")
    assert mode == "smoke_org_short_lived"
    assert org_id == "f07e57c0-1501-4000-8000-c04e57a00001"
    assert claims["sub"] == "a9f1240f-910a-42ca-aebf-38caeac288c3"
    assert claims["exp"] - claims["iat"] == vpp.SMOKE_TOKEN_TTL_SECONDS <= 600
    assert claims["iss"] == "https://example.supabase.co/auth/v1"


def test_smoke_org_token_expires(monkeypatch):
    monkeypatch.setenv("PLAYS_ACCEPTANCE_AUTH", "smoke-org")
    token, _org = vpp.smoke_org_session(now=1_000_000)
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, SECRET, algorithms=["HS256"], audience="authenticated")


def test_smoke_org_mode_refuses_the_operator_org(monkeypatch):
    monkeypatch.setenv("PLAYS_ACCEPTANCE_AUTH", "smoke-org")
    monkeypatch.setenv("ISOLATED_CONVERSATION_TEST_ORG_ID", FORBIDDEN_OPERATOR_ORG_ID)
    with pytest.raises(ConversationWriteBlockedError):
        vpp.session()


def test_owner_session_still_takes_precedence(monkeypatch):
    monkeypatch.setenv("PLAYS_ACCEPTANCE_AUTH", "smoke-org")
    monkeypatch.setenv("PLATFORM_LIVE_BEARER_TOKEN", "owner-token")
    monkeypatch.setenv("PLATFORM_LIVE_ORG_ID", "owner-org")
    assert vpp.session() == ("owner-token", "owner-org", "owner_session")


def test_no_credentials_fails_closed():
    with pytest.raises(SystemExit, match="missing credentials"):
        vpp.session()
