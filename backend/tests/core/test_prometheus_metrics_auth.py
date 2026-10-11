"""/metrics requires the internal secret header when PROMETHEUS_ENABLED is on."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.observability.apm as apm
from app.config import get_settings


def test_metrics_not_mounted_when_disabled(monkeypatch) -> None:
    monkeypatch.delenv("PROMETHEUS_ENABLED", raising=False)
    app = FastAPI()
    apm.setup_prometheus(app)
    assert TestClient(app).get("/metrics").status_code == 404


@pytest.fixture(scope="module")
def metrics_client():
    pytest.importorskip("prometheus_client")
    from prometheus_client import REGISTRY

    mp = pytest.MonkeyPatch()
    mp.setenv("PROMETHEUS_ENABLED", "1")
    app = FastAPI()
    apm.setup_prometheus(app)
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(internal_api_secret="s3cret")
    yield TestClient(app)
    for collector in (apm._HTTP_REQUESTS, apm._HTTP_LATENCY):
        if collector is not None:
            try:
                REGISTRY.unregister(collector)
            except KeyError:
                pass
    mp.undo()


def test_metrics_rejects_missing_secret(metrics_client) -> None:
    assert metrics_client.get("/metrics").status_code == 401


def test_metrics_rejects_wrong_secret(metrics_client) -> None:
    assert metrics_client.get("/metrics", headers={"X-Internal-Secret": "nope"}).status_code == 401


def test_metrics_served_with_internal_secret(metrics_client) -> None:
    resp = metrics_client.get("/metrics", headers={"X-Internal-Secret": "s3cret"})
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
