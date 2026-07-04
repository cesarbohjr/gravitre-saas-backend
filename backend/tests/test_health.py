"""Health endpoint smoke tests."""
from __future__ import annotations


async def test_health_returns_ok_with_timestamp(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"ok", "degraded"}
    assert "timestamp" in data
    assert data["timestamp"]
    assert "version" in data
    assert "ai_disabled" in data
    assert "checks" in data
    assert "database" in data["checks"]
