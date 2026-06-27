from __future__ import annotations

from types import SimpleNamespace

from app.routers.connector_oauth import _frontend_redirect


def test_frontend_redirect_builds_app_url():
    settings = SimpleNamespace(public_app_url="https://gravitre.app")
    url = _frontend_redirect(
        settings,
        "/connectors",
        {"oauth": "success", "provider": "slack", "connectorId": "abc"},
    )
    assert url.startswith("https://gravitre.app/connectors?")
    assert "oauth=success" in url
    assert "provider=slack" in url
