"""Shared gateway enforcement, independent of the browser library.

These tests exercise the real gateway HTTP handler for both proposed adapter
identities. They do not claim Playwright production worker certification.
"""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from app.services.native_runtime import gateway


@pytest.mark.parametrize("adapter", ["browser_use", "playwright"])
def test_comparison_gateway_denies_invalid_tokens_without_authorizing(monkeypatch, adapter):
    authorizations = []
    monkeypatch.setattr(gateway, "CONFIG", {"engine_token": "synthetic-token"})
    monkeypatch.setattr(gateway, "control", lambda *args: authorizations.append(args))
    server = ThreadingHTTPServer(("127.0.0.1", 0), gateway.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
        for supplied in ("wrong-token", ""):
            req = Request(url, data=json.dumps({"model": "ignored", "messages": [],
                "adapter": adapter}).encode(), method="POST",
                headers={"Authorization": "Bearer " + supplied, "Content-Type": "application/json"})
            with pytest.raises(HTTPError) as failure:
                urlopen(req, timeout=3)
            assert failure.value.code == 403
            assert json.load(failure.value)["error"] == "native_authorization_required"
        assert authorizations == []
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


@pytest.mark.parametrize("adapter", ["browser_use", "playwright"])
def test_comparison_gateway_rejects_unapproved_connect_destination(monkeypatch, adapter):
    # Exact CONNECT host allowlist is enforced before any authority callback or
    # network resolution. The adapter label is a matrix identifier only.
    from unittest.mock import Mock
    monkeypatch.setattr(gateway, "CONFIG", {"allowed_hosts": ["www.selenium.dev"]})
    callback = Mock()
    monkeypatch.setattr(gateway, "control", callback)
    resolver = Mock(side_effect=AssertionError("must not resolve"))
    monkeypatch.setattr(gateway, "public_addresses", resolver)
    handler = object.__new__(gateway.Handler)
    handler.path = "169.254.169.254:443"
    handler.send_error = Mock()
    handler.do_CONNECT()
    handler.send_error.assert_called_once_with(403, "Native destination blocked")
    callback.assert_not_called()
    resolver.assert_not_called()



@pytest.mark.parametrize("adapter", ["browser_use", "playwright"])
def test_dispatch_reauthorization_requires_current_lease_and_correct_engine_token(monkeypatch, adapter):
    from unittest.mock import Mock
    control = Mock(return_value={"authorized": True})
    monkeypatch.setattr(gateway, "CONFIG", {"engine_token": "approved-fixture-token"})
    monkeypatch.setattr(gateway, "control", control)
    server = ThreadingHTTPServer(("127.0.0.1", 0), gateway.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/authorize"
        def post(token):
            return Request(url, data=b"{}", method="POST",
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with pytest.raises(HTTPError) as blocked:
            urlopen(post("wrong-token"), timeout=3)
        assert blocked.value.code == 403
        control.assert_not_called()
        with urlopen(post("approved-fixture-token"), timeout=3) as response:
            assert json.load(response)["authorized"] is True
        control.assert_called_once_with("authorize", {})
        control.side_effect = PermissionError("revoked")
        with pytest.raises(HTTPError) as revoked:
            urlopen(post("approved-fixture-token"), timeout=3)
        assert revoked.value.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
