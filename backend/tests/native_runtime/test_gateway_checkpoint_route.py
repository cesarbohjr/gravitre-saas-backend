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
