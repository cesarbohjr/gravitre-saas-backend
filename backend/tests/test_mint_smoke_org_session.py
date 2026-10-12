"""The Plays acceptance session is short-lived, masked, read-only and smoke-org only."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest

from app.services.conversation_write_guard import (
    FORBIDDEN_OPERATOR_ORG_ID,
    ConversationWriteBlockedError,
    isolated_conversation_test_org_id,
)

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "mint_smoke_org_session", REPO / "scripts" / "mint_smoke_org_session.py"
)
mint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mint)

SECRET = "mint-smoke-session-test-secret-32-bytes!"
ENV = {"SUPABASE_URL": "https://example.supabase.co", "SUPABASE_JWT_SECRET": SECRET}


class _Query:
    def __init__(self, rows, log, table):
        self._rows, self._log, self._table = rows, log, table

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        self._log.append(("select", self._table))
        return SimpleNamespace(data=self._rows)

    def __getattr__(self, name):  # insert/update/delete/upsert must never be called
        raise AssertionError(f"write attempted: {self._table}.{name}")


class _Client:
    def __init__(self, *, flagged=True, member=True):
        self.log: list[tuple[str, str]] = []
        self._orgs = [
            {"id": "x", "settings": {"isolated_conversation_test_org": flagged}}
        ]
        self._members = [{"id": "m"}] if member else []

    def table(self, name):
        rows = self._orgs if name == "organizations" else self._members
        return _Query(rows, self.log, name)


@pytest.fixture(autouse=True)
def _no_overrides(monkeypatch):
    monkeypatch.delenv("ISOLATED_CONVERSATION_TEST_ORG_ID", raising=False)
    monkeypatch.delenv("ISOLATED_CONVERSATION_TEST_USER_ID", raising=False)


def test_session_is_ten_minutes_for_the_guard_resolved_smoke_actor():
    client = _Client()
    token, org_id = mint.mint_session(dict(ENV), client)
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], audience="authenticated")
    assert org_id == isolated_conversation_test_org_id()
    assert claims["exp"] - claims["iat"] == mint.TOKEN_TTL_SECONDS == 600
    assert claims["role"] == "authenticated"
    assert claims["iss"] == "https://example.supabase.co/auth/v1"
    assert {t for _op, t in client.log} == {"organizations", "organization_members"}


def test_token_expires():
    token = mint.mint_token(
        supabase_url="https://e.supabase.co",
        secret=SECRET,
        user_id="u",
        email="e",
        now=1_000,
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, SECRET, algorithms=["HS256"], audience="authenticated")


def test_operator_org_is_refused(monkeypatch):
    monkeypatch.setenv("ISOLATED_CONVERSATION_TEST_ORG_ID", FORBIDDEN_OPERATOR_ORG_ID)
    with pytest.raises(ConversationWriteBlockedError):
        mint.mint_session(
            {**ENV, "ISOLATED_CONVERSATION_TEST_ORG_ID": FORBIDDEN_OPERATOR_ORG_ID},
            _Client(),
        )


@pytest.mark.parametrize("client", [_Client(flagged=False), _Client(member=False)])
def test_unflagged_org_or_missing_membership_fails_closed_without_provisioning(client):
    with pytest.raises(mint.SmokeSessionError):
        mint.mint_session(dict(ENV), client)


def test_missing_signing_secret_fails_closed():
    with pytest.raises(mint.SmokeSessionError, match="SUPABASE_JWT_SECRET"):
        mint.mint_session({"SUPABASE_URL": ENV["SUPABASE_URL"]}, _Client())


def test_github_export_masks_before_writing_and_never_prints_the_token_elsewhere(
    tmp_path, capsys
):
    env_file = tmp_path / "github_env"
    mint.export_to_github("tok.en.value", "org-1", env_file)
    out = capsys.readouterr().out
    assert out == "::add-mask::tok.en.value\n"
    assert env_file.read_text().splitlines() == [
        "PLATFORM_LIVE_BEARER_TOKEN=tok.en.value",
        "PLATFORM_LIVE_ORG_ID=org-1",
        "PLATFORM_LIVE_AUTH_MODE=smoke_org_short_lived",
    ]


def test_workflows_mint_instead_of_reading_a_stored_bearer():
    for name in ("plays-production-acceptance.yml", "plays-datasets-live-proof.yml"):
        text = (REPO / ".github" / "workflows" / name).read_text()
        assert "secrets.PLATFORM_LIVE_BEARER_TOKEN" not in text
        assert "secrets.PLATFORM_LIVE_ORG_ID" not in text
        assert "scripts/mint_smoke_org_session.py --github-env" in text
        assert 'echo "PLATFORM_LIVE_BEARER_TOKEN=" >> "$GITHUB_ENV"' in text
        assert "f07e57c0" not in text
    assert (
        "pip install -r backend/requirements-dev.txt"
        in (
            REPO / ".github" / "workflows" / "plays-production-acceptance.yml"
        ).read_text()
    )
