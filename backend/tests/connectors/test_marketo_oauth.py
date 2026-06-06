from __future__ import annotations

from types import SimpleNamespace

from app.connectors.marketo_oauth import (
    marketo_identity_base,
    marketo_oauth_configured,
    normalize_vendor,
)


def test_normalize_vendor_marketo():
    assert normalize_vendor("Marketo") == "marketo"
    assert normalize_vendor("adobe_marketo") == "marketo"


def test_marketo_oauth_configured():
    settings = SimpleNamespace(marketo_client_id="cid", marketo_client_secret="sec")
    assert marketo_oauth_configured(settings) is True


def test_marketo_identity_base():
    assert marketo_identity_base("abc-123") == "https://abc-123.mktorest.com"
