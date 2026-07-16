"""F3/H3 — sandbox/demo endpoint resolution defaults (governance guard)."""
from __future__ import annotations

from app.services.gusto_tools import GUSTO_DEMO_BASE, GUSTO_PRODUCTION_BASE, resolve_gusto_api_base
from app.services.plaid_tools import (
    PLAID_PRODUCTION_BASE,
    PLAID_SANDBOX_BASE,
    resolve_plaid_api_base,
)


def test_plaid_defaults_to_sandbox():
    base, env = resolve_plaid_api_base()
    assert env == "sandbox"
    assert base == PLAID_SANDBOX_BASE


def test_plaid_production_only_when_explicit():
    base, env = resolve_plaid_api_base(params={"plaid_env": "production"})
    assert env == "production"
    assert base == PLAID_PRODUCTION_BASE


def test_gusto_defaults_to_demo():
    base, env = resolve_gusto_api_base()
    assert env == "demo"
    assert base == GUSTO_DEMO_BASE


def test_gusto_production_only_when_explicit():
    base, env = resolve_gusto_api_base(params={"gusto_env": "production"})
    assert env == "production"
    assert base == GUSTO_PRODUCTION_BASE
