"""Existing knowledge syncs keep running by default; the owner switch holds them.

EXISTING_INGESTION_REQUIRES_LIFECYCLE (default false) is the owner's decision. Off,
nothing about today's Notion, Confluence, HubSpot, Zendesk and Workday syncs changes.
On, they wait for the lifecycle prerequisites and are refused for providers without
a wired revoke call, before any sync job row or ingest job is written.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.config import Settings, get_settings
from app.services import knowledge_sync_service as ks
from app.services.ingestion_interlock import LIFECYCLE_PREREQUISITES, IngestionHeldError

LIFECYCLE_ON = dict(LIFECYCLE_PREREQUISITES)
GATED = SimpleNamespace(existing_ingestion_requires_lifecycle=True)
GATED_READY = SimpleNamespace(existing_ingestion_requires_lifecycle=True, **LIFECYCLE_ON)
ORG = "11111111-1111-4111-8111-111111111111"
CONNECTOR = "33333333-3333-4333-8333-333333333333"


def _connector(vendor: str, cid: str = "c1") -> dict:
    return {"id": cid, "org_id": ORG, "type": vendor, "environment": "production", "config": {}}


class _Untouchable:
    """A client that fails the test if anything reads or writes through it."""

    def table(self, name):
        raise AssertionError(f"held ingestion touched table {name}")

    def rpc(self, name, *_a):
        raise AssertionError(f"held ingestion called rpc {name}")


def _run_scheduled(settings, connectors):
    with patch.object(ks, "list_due_knowledge_connectors", return_value=connectors) as due, patch.object(
        ks, "create_knowledge_sync_job", side_effect=lambda *a, **k: {"id": f"job-{k['connector_id']}"}
    ) as create, patch.object(
        ks, "execute_knowledge_sync_job", return_value={"pages_synced": 1, "jobs_queued": 1}
    ) as execute:
        summary = ks.run_scheduled_knowledge_syncs(settings, client=object())
    return summary, due, create, execute


def test_scheduled_sync_runs_as_before_with_default_settings():
    # Lifecycle prerequisites are all missing by default and sync still runs: no silent switch-off.
    summary, _due, create, execute = _run_scheduled(Settings(), [_connector("notion"), _connector("zendesk", "c2")])
    assert summary["processed"] == 2 and summary["held"] == 0
    assert create.call_count == 2 and execute.call_count == 2


def test_owner_switch_without_lifecycle_holds_the_whole_scheduled_run():
    summary, due, create, execute = _run_scheduled(GATED, [_connector("hubspot")])
    assert summary["processed"] == 0 and summary["held_reason"].startswith("lifecycle_prerequisites_missing:")
    due.assert_not_called()
    create.assert_not_called()
    execute.assert_not_called()


def test_owner_switch_with_lifecycle_holds_only_providers_without_revoke():
    connectors = [_connector("hubspot", "c-hs"), _connector("notion", "c-no"), _connector("zendesk", "c-zd")]
    summary, _due, create, execute = _run_scheduled(GATED_READY, connectors)
    assert summary["processed"] == 1 and summary["held"] == 2
    assert [c.kwargs["connector_id"] for c in create.call_args_list] == ["c-hs"]
    held = {o["connector_id"]: o["reason"] for o in summary["outcomes"] if o["status"] == "held"}
    assert held == {
        "c-no": "provider_revoke_not_supported:notion",
        "c-zd": "provider_revoke_not_supported:zendesk",
    }
    assert execute.call_count == 1


def test_manual_trigger_is_refused_before_a_sync_job_is_written():
    class _Client:
        def table(self, name):
            assert name == "connectors"

            class _Q:
                def __getattr__(self, _n):
                    return lambda *a, **k: self

                def execute(self):
                    return SimpleNamespace(data=[_connector("confluence", CONNECTOR)])

            return _Q()

    with patch.object(ks, "create_knowledge_sync_job") as create, pytest.raises(IngestionHeldError):
        ks.trigger_connector_knowledge_sync(_Client(), GATED_READY, ORG, CONNECTOR, actor_id="u1")
    create.assert_not_called()


@pytest.mark.parametrize(
    ("module", "runner"),
    [
        ("app.services.notion_sync_service", "run_notion_sync"),
        ("app.services.confluence_sync_service", "run_confluence_sync"),
        ("app.services.workday_sync_service", "run_workday_sync"),
        ("app.services.hubspot_knowledge_sync_service", "run_hubspot_knowledge_sync"),
        ("app.services.zendesk_knowledge_sync_service", "run_zendesk_knowledge_sync"),
    ],
)
def test_every_sync_runner_is_held_by_the_owner_switch(module, runner):
    # Per-vendor /run routes and webhooks call these directly, so the guard lives here too.
    import importlib

    fn = getattr(importlib.import_module(module), runner)
    with pytest.raises(IngestionHeldError):
        fn(_Untouchable(), ORG, CONNECTOR, GATED, actor_id="u1")


@pytest.mark.parametrize("vendor", ["notion", "confluence", "workday", "zendesk"])
def test_runners_for_providers_without_revoke_stay_held_when_lifecycle_is_on(vendor):
    import importlib

    module, runner = {
        "notion": ("app.services.notion_sync_service", "run_notion_sync"),
        "confluence": ("app.services.confluence_sync_service", "run_confluence_sync"),
        "workday": ("app.services.workday_sync_service", "run_workday_sync"),
        "zendesk": ("app.services.zendesk_knowledge_sync_service", "run_zendesk_knowledge_sync"),
    }[vendor]
    fn = getattr(importlib.import_module(module), runner)
    with pytest.raises(IngestionHeldError, match=f"provider_revoke_not_supported:{vendor}"):
        fn(_Untouchable(), ORG, CONNECTOR, GATED_READY, actor_id="u1")


# ------------------------------------------------------------------ HTTP: held answers 503


def _route_settings(**kw) -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
        openai_api_key="sk-test-openai",
        **kw,
    )


class _ConnectorClient:
    def __init__(self, vendor: str) -> None:
        self.vendor = vendor
        self.inserted: list[str] = []

    def table(self, name):
        client = self

        class _Q:
            def __getattr__(self, _n):
                return lambda *a, **k: self

            def insert(self, *_a, **_k):
                client.inserted.append(name)
                return self

            def execute(self):
                return SimpleNamespace(data=[{**_connector(client.vendor, CONNECTOR), "status": "active"}])

        return _Q()


@pytest.fixture
def overrides():
    from app.auth.dependencies import (
        get_environment_context,
        get_org_context,
        require_admin,
    )
    from app.main import app

    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, ORG)
    app.dependency_overrides[get_org_context] = lambda: ORG
    app.dependency_overrides[get_environment_context] = lambda: "production"
    yield app
    for dep in (require_admin, get_org_context, get_environment_context, get_settings):
        app.dependency_overrides.pop(dep, None)


@pytest.mark.parametrize("path", ["/api/admin/knowledge/connectors/{c}/sync", "/api/connectors/{c}/sync"])
async def test_manual_sync_routes_answer_503_when_held(async_client, overrides, monkeypatch, path):
    import app.routers.connectors as connectors_router
    import app.routers.knowledge_sync as knowledge_router

    client = _ConnectorClient("notion")
    monkeypatch.setattr(knowledge_router, "shared_service_client", lambda *a, **k: client)
    monkeypatch.setattr(connectors_router, "shared_service_client", lambda *a, **k: client)
    overrides.dependency_overrides[get_settings] = lambda: _route_settings(existing_ingestion_requires_lifecycle=True)
    resp = await async_client.post(path.format(c=CONNECTOR), json={})
    assert resp.status_code == 503
    assert resp.json()["code"] == "INGESTION_HELD"
    assert client.inserted == []
