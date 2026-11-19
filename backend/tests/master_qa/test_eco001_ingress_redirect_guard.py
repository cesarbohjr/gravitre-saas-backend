"""ECO-001 read-only ingress probe must never follow redirects off the supplied host."""

import json
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
    payload = {
        "checks": {"database": "healthy"},
        "unified_turn_live_enabled": True,
        "environment": "production-canary",
        "git_sha": "a" * 40,
    }
    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: (200, json.dumps(payload).encode()))
    with pytest.raises(ValueError, match="production or unidentified runtime"):
        run("https://qa.example.test", "a" * 40, {})


@pytest.mark.parametrize("fixture_status", [200, 302, 404])
def test_signed_fixture_sends_token_only_after_anonymous_denial(monkeypatch, fixture_status):
    calls = []
    token = "test.actor.signature"
    fixture = "qa-owned-conversation"

    def get(url, headers=None):
        calls.append((url, headers))
        if url.endswith("/health"):
            return 200, json.dumps({
                "checks": {"database": "healthy"},
                "unified_turn_live_enabled": True,
                "environment": "qa",
                "git_sha": "a" * 40,
            }).encode()
        if headers:
            return fixture_status, b'{"task_state":{"private":"fixture"},"execution_result":null}'
        return 401, b""

    monkeypatch.setattr(probe, "get", get)
    if fixture_status == 200:
        report = run(probe.QA_ORIGIN, "a" * 40, {}, qa_bearer=token, qa_conversation=fixture)
        assert report["signed_fixture_statuses"] == {"anonymous": 401, "authenticated": 200}
        assert all(value not in json.dumps(report) for value in (token, fixture, "private"))
    else:
        with pytest.raises(ValueError, match=f"Signed fixture GET returned HTTP {fixture_status}"):
            run(probe.QA_ORIGIN, "a" * 40, {}, qa_bearer=token, qa_conversation=fixture)

    assert calls[-2:] == [
        (f"{probe.QA_ORIGIN}/api/assistant/conversation/{fixture}/state", None),
        (f"{probe.QA_ORIGIN}/api/assistant/conversation/{fixture}/state", {"Authorization": f"Bearer {token}"}),
    ]
    assert not any(headers for _, headers in calls[:-1])


@pytest.mark.parametrize(("base", "fixture"), [
    ("https://other.example.test", "qa-owned-conversation"),
    (probe.QA_ORIGIN, "../health"),
])
def test_signed_preflight_rejects_wrong_origin_or_route_before_network(monkeypatch, base, fixture):
    monkeypatch.setattr(probe, "get", lambda *args, **kwargs: pytest.fail("network should not run"))
    with pytest.raises(ValueError, match="isolated Railway QA origin|owned QA conversation fixture"):
        run(base, "a" * 40, {}, qa_bearer="test.actor.signature", qa_conversation=fixture)
