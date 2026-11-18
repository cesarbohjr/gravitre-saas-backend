"""ECO-001 read-only ingress probe must never follow redirects off the supplied host."""

from urllib.error import HTTPError
from urllib.request import Request

import pytest

# Load the backend-owned probe by file path. CI also exposes a repository-root
# "scripts" package, which otherwise shadows backend/scripts during collection.
import importlib.util
from pathlib import Path

_probe_path = Path(__file__).resolve().parents[2] / "scripts" / "eco001_deployed_ingress_preflight.py"
_spec = importlib.util.spec_from_file_location("eco001_deployed_ingress_preflight_test", _probe_path)
assert _spec is not None and _spec.loader is not None
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)
_RejectRedirects = probe._RejectRedirects
run = probe.run


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

    monkeypatch.setattr(probe, "get", lambda url, headers=None: (302, b""))
    with pytest.raises(ValueError, match="FastAPI /health returned HTTP 302"):
        run("https://qa.example.test", "a" * 40, {})


@pytest.mark.parametrize("sha", ["", "abc", "g" * 40, "a" * 39])
def test_preflight_rejects_non_exact_sha_before_network(monkeypatch, sha):

    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: pytest.fail("network should not run"))
    with pytest.raises(ValueError, match="full 40-character"):
        run("https://qa.example.test", sha, {})


@pytest.mark.parametrize("url", [
    "https://qa.example.test/health",
    "https://qa.example.test/?token=secret",
    "https://qa.example.test/#fragment",
])
def test_preflight_rejects_non_origin_url_before_network(monkeypatch, url):

    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: pytest.fail("network should not run"))
    with pytest.raises(ValueError, match="HTTPS origin"):
        run(url, "a" * 40, {})


def test_preflight_rejects_unknown_environment(monkeypatch):
    import json

    payload = {
        "checks": {"database": "healthy"},
        "unified_turn_live_enabled": True,
        "environment": "production-canary",
        "git_sha": "a" * 40,
    }
    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: (200, json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="production or unidentified runtime"):
        run("https://qa.example.test", "a" * 40, {})
