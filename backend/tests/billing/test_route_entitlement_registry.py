"""Meta-tests: every FastAPI route has an explicit tier-entitlement decision."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.billing.route_entitlement_registry import classify_all_routes, classify_route, gaps
from app.main import app

REPO = Path(__file__).resolve().parents[2]
INVENTORY = REPO / "docs" / "delivery" / "route-inventory.json"


def _runtime_routes() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if not path or str(path).startswith("/openapi") or str(path).startswith("/docs"):
            continue
        for method in sorted(methods):
            if method in {"HEAD", "OPTIONS"}:
                continue
            rows.append({"method": method, "path": str(path)})
    rows.sort(key=lambda r: (r["path"], r["method"]))
    return rows


def test_every_route_has_explicit_tier_classification():
    routes = _runtime_routes()
    decisions = classify_all_routes(routes)
    assert len(decisions) == len(routes)
    for decision in decisions:
        assert decision.tier_required in {"none", "control", "command"}
        assert decision.status in {"correctly_guarded", "correctly_unguarded", "gap_needs_guard"}


def test_no_route_in_codebase_lacks_explicit_tier_decision():
    routes = _runtime_routes()
    for route in routes:
        decision = classify_route(route["method"], route["path"])
        assert decision.status != "gap_needs_guard", f"Unclassified gap: {route['method']} {route['path']}"
    assert not gaps(classify_all_routes(routes))


def test_runtime_inventory_matches_saved_snapshot():
    if not INVENTORY.is_file():
        pytest.skip("Run scripts/extract-api-routes.py to refresh route-inventory.json")
    saved = json.loads(INVENTORY.read_text(encoding="utf-8"))
    runtime = _runtime_routes()
    saved_keys = {(r["method"], r["path"]) for r in saved}
    runtime_keys = {(r["method"], r["path"]) for r in runtime}
    assert runtime_keys == saved_keys, (
        f"Route inventory drift: added={runtime_keys - saved_keys} removed={saved_keys - runtime_keys}"
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/federation/partnerships"),
        ("POST", "/api/meson/interpret"),
        ("GET", "/api/ml/models"),
        ("POST", "/api/agent-swarm/start"),
        ("POST", "/api/agent-council/start"),
    ],
)
def test_node_tier_blocked_from_command_or_control_route(method: str, path: str):
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user, get_org_context, require_admin
    from app.config import Settings, get_settings
    from app.main import app
    from app.middleware.entitlements import TIER_FEATURES, TIER_LIMITS, get_entitlements_dependency

    client = TestClient(app)

    def _settings() -> Settings:
        return Settings(
            app_env="dev",
            supabase_url="https://test.supabase.co",
            supabase_anon_key="anon-test",
            supabase_service_role_key="service-role-test",
            supabase_jwt_secret="jwt-secret-test",
        )

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: "org-node"
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, "org-node")
    app.dependency_overrides[get_entitlements_dependency] = lambda: {
        "tier": "node",
        "status": "active",
        "seat_count": 1,
        "lite_seats": 0,
        "limits": dict(TIER_LIMITS["node"]),
        "features": dict(TIER_FEATURES["node"]),
        "addons": [],
        "usage": {},
    }
    try:
        response = client.request(method, path, json={})
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_command_tier_can_access_swarm_route():
    from unittest.mock import MagicMock, patch

    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user, get_org_context
    from app.config import Settings, get_settings
    from app.main import app
    from app.middleware.entitlements import TIER_FEATURES, TIER_LIMITS, get_entitlements_dependency

    client = TestClient(app)

    def _settings() -> Settings:
        return Settings(
            app_env="dev",
            supabase_url="https://test.supabase.co",
            supabase_anon_key="anon-test",
            supabase_service_role_key="service-role-test",
            supabase_jwt_secret="jwt-secret-test",
        )

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: "org-cmd"
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_entitlements_dependency] = lambda: {
        "tier": "command",
        "status": "active",
        "seat_count": 1,
        "lite_seats": 0,
        "limits": dict(TIER_LIMITS["command"]),
        "features": dict(TIER_FEATURES["command"]),
        "addons": [],
        "usage": {},
    }
    try:
        with patch("app.routers.agent_swarm.list_swarm_runs", return_value=[]):
            with patch("app.routers.agent_swarm.create_client", return_value=MagicMock()):
                response = client.get("/api/agent-swarm")
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
