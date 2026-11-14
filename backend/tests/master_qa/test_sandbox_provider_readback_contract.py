"""No-network contract tests for explicitly gated sandbox provider readback."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_readback():
    # The repository root also owns a 'scripts' package; load the backend
    # acceptance script by its verified path, not by an ambiguous package name.
    path = Path(__file__).resolve().parents[2] / "scripts" / "p27_sandbox_provider_readback.py"
    spec = importlib.util.spec_from_file_location("p27_sandbox_provider_readback", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sandbox_readback_refuses_unapproved_or_non_https(monkeypatch):
    readback = _load_readback()
    monkeypatch.setattr(
        readback, "_request",
        lambda *args, **kw: (_ for _ in ()).throw(AssertionError("network reached")),
    )
    with pytest.raises(RuntimeError, match="approval"):
        readback.verify(base="https://sandbox.invalid", allowed_host="sandbox.invalid",
                        token="fake-acceptance-token", approved=False)
    with pytest.raises(RuntimeError, match="HTTPS"):
        readback.verify(base="http://sandbox.invalid", allowed_host="sandbox.invalid",
                        token="fake-acceptance-token", approved=True)
    with pytest.raises(RuntimeError, match="allowlisted"):
        readback.verify(base="https://production.invalid", allowed_host="sandbox.invalid",
                        token="fake-acceptance-token", approved=True)


def test_sandbox_readback_requires_independent_matching_provider_state(monkeypatch, capsys):
    readback = _load_readback()
    calls = []
    def fake_request(url, *, token, method, payload=None):
        calls.append((method, url, payload))
        if method == "POST":
            return {"id": "sandbox-entity-1",
                    "idempotency_key": payload["idempotency_key"]}
        return {"id": "sandbox-entity-1",
                "idempotency_key": calls[0][2]["idempotency_key"],
                "status": "applied"}
    monkeypatch.setattr(readback, "_request", fake_request)
    readback.verify(base="https://sandbox.invalid/api",
                    allowed_host="sandbox.invalid",
                    token="fake-acceptance-token", approved=True)
    assert [method for method, _, _ in calls] == ["POST", "GET", "POST"]
    assert "SANDBOX_LIVE" in capsys.readouterr().out


def test_sandbox_readback_fails_on_mismatched_authoritative_get(monkeypatch):
    readback = _load_readback()
    def fake_request(url, *, token, method, payload=None):
        if method == "POST":
            return {"id": "sandbox-entity-1",
                    "idempotency_key": payload["idempotency_key"]}
        return {"id": "another-resource", "idempotency_key": "mismatch",
                "status": "applied"}
    monkeypatch.setattr(readback, "_request", fake_request)
    with pytest.raises(RuntimeError, match="independent readback"):
        readback.verify(base="https://sandbox.invalid",
                        allowed_host="sandbox.invalid",
                        token="fake-acceptance-token", approved=True)


@pytest.mark.parametrize("body,expected", [
    (b'{"portalId":343328749,"accountType":"STANDARD"}',
     {"portalId": 343328749, "accountType": "STANDARD"}),
    (b"", {}),
])
def test_http_helper_returns_decoded_json_or_empty_204(monkeypatch, body, expected):
    """Exercise the actual shared HTTP helper, not a mocked _request."""
    readback = _load_readback()

    class FakeResponse:
        def __init__(self):
            self.read_count = 0

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size):
            self.read_count += 1
            return body if self.read_count == 1 else b""

    class FakeOpener:
        def open(self, request, timeout):
            assert timeout == 15
            assert request.get_method() == "GET"
            return FakeResponse()

    monkeypatch.setattr(readback.urllib.request, "build_opener",
                        lambda *handlers: FakeOpener())
    result = readback._request("https://api.hubapi.com/account-info/v3/details",
                               token="fake-acceptance-token", method="GET")
    assert result == expected
    assert isinstance(result, dict)


def test_http_helper_rejects_oversized_provider_response(monkeypatch):
    readback = _load_readback()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self, size):
            return b'{"ok":true}' if size == 32768 else b"x"

    class FakeOpener:
        def open(self, request, timeout):
            return FakeResponse()

    monkeypatch.setattr(readback.urllib.request, "build_opener",
                        lambda *handlers: FakeOpener())
    with pytest.raises(RuntimeError, match="maximum size"):
        readback._request("https://api.hubapi.com/account-info/v3/details",
                          token="fake-acceptance-token", method="GET")
