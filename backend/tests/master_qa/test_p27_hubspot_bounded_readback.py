"""P27: transient read-after-write 404s cannot trigger another write."""
import urllib.error
from unittest.mock import Mock
import pytest
from scripts import p27_hubspot_sandbox_readback as mod


def test_transient_404_is_bounded_and_read_only(monkeypatch):
    calls = []
    def request(url, *, token, method):
        calls.append(method)
        if len(calls) < 3:
            raise urllib.error.HTTPError(url, 404, "not yet visible", {}, None)
        return {"id": "123"}
    monkeypatch.setattr(mod, "_request", request)
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    assert mod._get_with_bounded_404_retry("https://example.invalid", token="secret") == {"id": "123"}
    assert calls == ["GET", "GET", "GET"]


def test_persistent_404_fails_closed(monkeypatch):
    calls = []
    def request(url, *, token, method):
        calls.append(method)
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)
    monkeypatch.setattr(mod, "_request", request)
    monkeypatch.setattr(mod.time, "sleep", lambda _: None)
    with pytest.raises(urllib.error.HTTPError) as exc:
        mod._get_with_bounded_404_retry("https://example.invalid", token="secret")
    assert exc.value.code == 404
    assert calls == ["GET"] * 5


def test_non_404_does_not_retry(monkeypatch):
    calls = []
    def request(url, *, token, method):
        calls.append(method)
        raise urllib.error.HTTPError(url, 403, "forbidden", {}, None)
    monkeypatch.setattr(mod, "_request", request)
    with pytest.raises(urllib.error.HTTPError) as exc:
        mod._get_with_bounded_404_retry("https://example.invalid", token="secret")
    assert exc.value.code == 403
    assert calls == ["GET"]
