"""ECO-001 read-only ingress probe must never follow redirects off the supplied host."""

from urllib.error import HTTPError
from urllib.request import Request

import pytest

from scripts.eco001_deployed_ingress_preflight import _RejectRedirects, run


def test_redirect_handler_refuses_cross_host_and_same_host_redirects():
    handler = _RejectRedirects()
    request = Request("https://qa.example.test/health")
    for destination in (
        "https://production.example.test/health",
        "https://qa.example.test/other",
        "http://qa.example.test/health",
    ):
        assert handler.redirect_request(request, None, 302, "Found", {}, destination) is None


def test_redirect_status_fails_health_identity_preflight(monkeypatch):
    from scripts import eco001_deployed_ingress_preflight as probe

    monkeypatch.setattr(probe, "get", lambda url, headers=None: (302, b""))
    with pytest.raises(ValueError, match="FastAPI /health returned HTTP 302"):
        run("https://qa.example.test", "a" * 40, {})


@pytest.mark.parametrize("sha", ["", "abc", "g" * 40, "a" * 39])
def test_preflight_rejects_non_exact_sha_before_network(monkeypatch, sha):
    from scripts import eco001_deployed_ingress_preflight as probe

    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: pytest.fail("network should not run"))
    with pytest.raises(ValueError, match="full 40-character"):
        run("https://qa.example.test", sha, {})


@pytest.mark.parametrize("url", [
    "https://qa.example.test/health",
    "https://qa.example.test/?token=secret",
    "https://qa.example.test/#fragment",
])
def test_preflight_rejects_non_origin_url_before_network(monkeypatch, url):
    from scripts import eco001_deployed_ingress_preflight as probe

    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: pytest.fail("network should not run"))
    with pytest.raises(ValueError, match="HTTPS origin"):
        run(url, "a" * 40, {})


def test_preflight_rejects_unknown_environment(monkeypatch):
    import json
    from scripts import eco001_deployed_ingress_preflight as probe

    payload = {
        "checks": {"database": "healthy"},
        "unified_turn_live_enabled": True,
        "environment": "production-canary",
        "git_sha": "a" * 40,
    }
    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: (200, json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="production or unidentified runtime"):
        run("https://qa.example.test", "a" * 40, {})
