"""Regression: the isolated gateway must forward authenticated checkpoints."""
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from app.services.native_runtime import gateway


def test_gateway_checkpoint_routes_only_under_engine_capability(monkeypatch):
    captured=[]
    monkeypatch.setattr(gateway,"CONFIG",{"engine_token":"test-engine"})
    def trusted_control(operation,payload):
        captured.append((operation,payload))
        assert operation=="checkpoint"
        assert payload["sequence"]==0
        assert payload["checkpoint"]["before_effect"] is True
        return {"persisted":True}
    monkeypatch.setattr(gateway,"control",trusted_control)
    server=ThreadingHTTPServer(("127.0.0.1",0),gateway.Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        url=f"http://127.0.0.1:{server.server_port}/checkpoint"
        payload={"sequence":0,"checkpoint":{"before_effect":True}}
        def request(token):
            return Request(url,data=json.dumps(payload).encode(),
                headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},
                method="POST")
        with pytest.raises(HTTPError) as error:
            urlopen(request("wrong"),timeout=3)
        assert error.value.code==403
        assert captured==[]
        with urlopen(request("test-engine"),timeout=3) as reply:
            assert reply.status==200
            assert json.load(reply)=={"persisted":True}
        assert captured==[("checkpoint",payload)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_pre_navigation_checkpoint_records_reviewed_target_without_dispatch():
    from app.services.native_runtime.engine import checkpoint_destination
    host=["www.selenium.dev"]
    target="https://www.selenium.dev/selenium/web/web-form.html"
    assert checkpoint_destination("about:blank",{"navigate":{"url":target}},host)==target
    assert checkpoint_destination(target,{"click":{"index":1}},host)==target
    tenant_target=target+"#isolated-case-capability"
    assert checkpoint_destination("about:blank",{"navigate":{"url":tenant_target}},host)==tenant_target


@pytest.mark.parametrize("intent",[
    {"navigate":{"url":"http://www.selenium.dev"}},
    {"navigate":{"url":"https://localhost/"}},
    {"navigate":{"url":"https://www.selenium.dev.evil.example/"}},
    {"navigate":{"url":"https://user@www.selenium.dev/"}},
    {"navigate":{"url":"https://www.selenium.dev:8443/"}},
    {"navigate":{"url":"https://www.selenium.dev/"},"click":{"index":1}},
    {"click":{"index":1}},
])
def test_pre_navigation_checkpoint_rejects_unsafe_destination(intent):
    from app.services.native_runtime.engine import checkpoint_destination
    with pytest.raises(PermissionError):
        checkpoint_destination("about:blank",intent,["www.selenium.dev"])
