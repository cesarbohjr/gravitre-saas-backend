"""Inbound trigger signing secrets are encrypted at rest in connectors.config."""
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.connectors.crypto import decrypt_secret, encrypt_secret
from app.services import connector_webhook_secret_store as store
from app.services import pagerduty_trigger_service as pd
from app.services import salesforce_trigger_service as sf
from app.services import segment_trigger_service as seg

KEY = "b" * 64
SETTINGS = SimpleNamespace(connector_secrets_encryption_key=KEY)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "get_settings", lambda: SETTINGS)


class _Q:
    def __init__(self, db: "_DB") -> None:
        self.db, self.op, self.payload = db, "select", None

    def select(self, *_a):
        return self

    def eq(self, *_a):
        return self

    def limit(self, *_a):
        return self

    def order(self, *_a):
        return self

    def range(self, *_a):
        return self

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def execute(self):
        if self.op == "update":
            self.db.writes.append(json.loads(json.dumps(self.payload)))
            self.db.config = self.payload["config"]
            return SimpleNamespace(data=[])
        return SimpleNamespace(data=[{"id": "c1", "org_id": "o1", "config": dict(self.db.config)}])


class _DB:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.writes: list = []

    def table(self, _name):
        return _Q(self)


def _no_plaintext(config: dict[str, Any], secret: str) -> None:
    assert secret not in json.dumps(config)
    for key in store.SECRET_KEYS:
        assert key not in config


@pytest.mark.parametrize("svc", [pd, sf, seg])
def test_generated_secret_is_stored_encrypted_only(svc):
    db = _DB({})
    secret = svc.ensure_connector_webhook_secret(db, "o1", "c1")
    assert len(secret) == 64
    _no_plaintext(db.config, secret)
    assert decrypt_secret(db.config["webhook_secret_encrypted"], KEY) == secret
    # Inbound verification reads the same value back.
    assert svc.get_connector_webhook_secret({"config": db.config}) == secret
    # A second ensure returns the same secret without rewriting the row.
    assert svc.ensure_connector_webhook_secret(db, "o1", "c1") == secret
    assert len(db.writes) == 1


@pytest.mark.parametrize("svc", [pd, sf, seg])
def test_legacy_plaintext_still_verifies_then_is_sealed(svc):
    legacy = {"webhook_secret": "legacy-plain"}
    assert svc.get_connector_webhook_secret({"config": legacy}) == "legacy-plain"
    db = _DB(dict(legacy))
    assert svc.ensure_connector_webhook_secret(db, "o1", "c1") == "legacy-plain"
    _no_plaintext(db.config, "legacy-plain")
    assert svc.get_connector_webhook_secret({"config": db.config}) == "legacy-plain"


def test_pagerduty_signing_secret_keeps_precedence_after_sealing():
    db = _DB({"webhook_secret": "ours", "pagerduty_signing_secret": "theirs"})
    assert pd.ensure_connector_webhook_secret(db, "o1", "c1") == "theirs"
    _no_plaintext(db.config, "theirs")
    assert "ours" not in json.dumps(db.config)
    assert pd.get_connector_webhook_secret({"config": db.config}) == "theirs"


def test_segment_generation_writes_both_keys_encrypted():
    db = _DB({})
    secret = seg.ensure_connector_webhook_secret(db, "o1", "c1")
    assert decrypt_secret(db.config["segment_webhook_secret_encrypted"], KEY) == secret
    assert decrypt_secret(db.config["webhook_secret_encrypted"], KEY) == secret


def test_undecryptable_ciphertext_fails_closed():
    other = encrypt_secret("x", "c" * 64)
    assert sf.get_connector_webhook_secret({"config": {"webhook_secret_encrypted": other}}) == ""


def test_without_key_behaves_as_before(monkeypatch):
    import app.config as cfg

    monkeypatch.setattr(cfg, "get_settings", lambda: SimpleNamespace(connector_secrets_encryption_key=""))
    db = _DB({})
    secret = sf.ensure_connector_webhook_secret(db, "o1", "c1")
    assert db.config["webhook_secret"] == secret


def test_backfill_dry_run_counts_without_writing_and_never_returns_values():
    db = _DB({"webhook_secret": "p1"})
    out = store.seal_plaintext_webhook_secrets(db, SETTINGS, dry_run=True)
    assert out == {"scanned": 1, "with_plaintext": 1, "sealed": 0}
    assert db.writes == []
    assert "p1" not in json.dumps(out)
    out = store.seal_plaintext_webhook_secrets(db, SETTINGS, dry_run=False)
    assert out["sealed"] == 1
    _no_plaintext(db.config, "p1")
