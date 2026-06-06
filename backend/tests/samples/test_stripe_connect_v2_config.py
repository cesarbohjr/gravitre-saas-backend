"""Config validation for Stripe Connect v2 sample."""
from __future__ import annotations

import os

import pytest

from app.samples.stripe_connect_v2.config import SampleConfigError, load_config


def test_load_config_requires_stripe_secret_key(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("STRIPE_CONNECT_THIN_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_CONNECT_SAMPLE_BASE_URL", "http://localhost:8000")
    with pytest.raises(SampleConfigError, match="STRIPE_SECRET_KEY"):
        load_config()


def test_load_config_requires_thin_webhook_secret(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.delenv("STRIPE_CONNECT_THIN_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("STRIPE_CONNECT_SAMPLE_BASE_URL", "http://localhost:8000")
    with pytest.raises(SampleConfigError, match="STRIPE_CONNECT_THIN_WEBHOOK_SECRET"):
        load_config()


def test_load_config_success(monkeypatch, tmp_path):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("STRIPE_CONNECT_THIN_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setenv("STRIPE_CONNECT_SAMPLE_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("STRIPE_CONNECT_SAMPLE_STORE_PATH", str(tmp_path / "store.json"))
    cfg = load_config()
    assert cfg.platform_fee_percent == 10
