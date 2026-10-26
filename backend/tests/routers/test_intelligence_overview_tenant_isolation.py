"""Tenant boundaries and approval scopes for Overview endpoints."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from app.routers import intelligence_overview as mod

class Query:
    def __init__(self, rows):
        self.rows, self.filters = rows, {}
    def select(self, *_): return self
    def eq(self, k, v): self.filters[k] = v; return self
    def limit(self, *_): return self
    def execute(self):
        return SimpleNamespace(data=[r for r in self.rows if all(r.get(k) == v for k, v in self.filters.items())])

class Client:
    def __init__(self, rows): self.rows = rows
    def table(self, name):
        assert name == "intelligence_overview_sweeps"
        return Query(self.rows)

def test_sweep_is_never_read_from_other_tenant(monkeypatch):
    rows = [{"id": "sweep-a", "org_id": "org-a", "status": "completed"}]
    monkeypatch.setattr(mod, "_db", lambda _settings: Client(rows))
    with pytest.raises(HTTPException) as exc:
        mod.sweep_status("sweep-a", "org-b", ({"sub": "user-b"}, None, "member"), object())
    assert exc.value.status_code == 404

def test_sweep_status_is_scoped_even_with_known_id(monkeypatch):
    rows = [{"id": "sweep-a", "org_id": "org-a", "status": "partial"}]
    monkeypatch.setattr(mod, "_db", lambda _settings: Client(rows))
    result = mod.sweep_status("sweep-a", "org-a", ({"sub": "user-a"}, None, "member"), object())
    assert result["sweep"]["org_id"] == "org-a"
    assert result["orchestrator_enabled"] is False

def test_no_unauthorized_unknown_capability_update(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        mod.update_profile(mod.ProfilePatch(capabilities={"nonexistent": {"mode": "balanced"}}),
                           "org-a", ({"sub": "admin"}, None, "admin"), object())
    assert exc.value.status_code == 422


def test_sweep_refuses_to_queue_when_worker_disabled(monkeypatch):
    monkeypatch.delenv("INTELLIGENCE_OVERVIEW_SWEEP_WORKER_ENABLED", raising=False)
    with pytest.raises(HTTPException) as exc:
        mod.request_sweep("org-a", ({"sub": "admin"}, None, "admin"), object())
    assert exc.value.status_code == 503
