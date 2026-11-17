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
        run("https://qa.example.test", "expected-sha", {})
