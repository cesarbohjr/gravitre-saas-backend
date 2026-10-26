"""Sweep admission cannot bypass the atomic database function."""
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from app.routers import intelligence_overview as overview

class RpcClient:
    def __init__(self, *, error=None):
        self.error = error
        self.calls = []
    def rpc(self, name, payload):
        self.calls.append((name, payload))
        return self
    def execute(self):
        if self.error:
            raise RuntimeError(self.error)
        return SimpleNamespace(data={"id": "s-1", "status": "queued"})


def test_atomic_admission_used(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_OVERVIEW_SWEEP_WORKER_ENABLED", "true")
    client = RpcClient()
    monkeypatch.setattr(overview, "_db", lambda _settings: client)
    monkeypatch.setattr(overview, "load_connected_connectors", lambda *_: [
        {"vendor": "hubspot", "executable": True},
    ])
    monkeypatch.setattr(overview, "write_audit_event", lambda *a, **kw: None)
    result = overview.request_sweep("org-a", ({"sub": "admin"}, None, "admin"), object())
    assert result["sweep"]["id"] == "s-1"
    assert len(client.calls) == 1
    name, payload = client.calls[0]
    assert name == "admit_intelligence_overview_sweep"
    assert payload["p_org_id"] == "org-a"


def test_quota_errors_are_explicit(monkeypatch):
    monkeypatch.setenv("INTELLIGENCE_OVERVIEW_SWEEP_WORKER_ENABLED", "true")
    monkeypatch.setattr(overview, "_db", lambda _settings: RpcClient(error="daily sweep quota exceeded"))
    monkeypatch.setattr(overview, "load_connected_connectors", lambda *_: [
        {"vendor": "hubspot", "executable": True},
    ])
    with pytest.raises(HTTPException) as exc:
        overview.request_sweep("org-a", ({"sub": "admin"}, None, "admin"), object())
    assert exc.value.status_code == 429
