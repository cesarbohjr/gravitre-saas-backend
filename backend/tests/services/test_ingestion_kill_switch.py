"""DISABLE_INGESTION stops every ingestion write path, and changes nothing while off."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.core.ingestion_kill_switch import (
    IngestionDisabledError,
    ensure_ingestion_enabled,
    ingestion_disabled,
)

ORG = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)
KILLED = SimpleNamespace(
    disable_ingestion=True,
    entity_writer_enabled=True,
    entity_observations_enabled=True,
    account_play_proposals_enabled=False,
)


def _untouched_client() -> MagicMock:
    client = MagicMock()
    client.table.side_effect = AssertionError("no table access while ingestion is disabled")
    client.rpc.side_effect = AssertionError("no rpc while ingestion is disabled")
    return client


# --------------------------------------------------------------------------- helper


def test_helper_only_trips_on_explicit_true() -> None:
    assert ingestion_disabled(SimpleNamespace(disable_ingestion=True)) is True
    assert ingestion_disabled(SimpleNamespace(disable_ingestion=False)) is False
    assert ingestion_disabled(SimpleNamespace()) is False
    assert ingestion_disabled(SimpleNamespace(disable_ingestion="true")) is False
    ensure_ingestion_enabled(SimpleNamespace(disable_ingestion=False), "test")
    with pytest.raises(IngestionDisabledError):
        ensure_ingestion_enabled(SimpleNamespace(disable_ingestion=True), "test")


def test_settings_default_is_off() -> None:
    from app.config import Settings

    assert Settings().disable_ingestion is False


# --------------------------------------------------------------------------- knowledge sync


def test_scheduled_knowledge_syncs_skip_without_touching_the_database() -> None:
    from app.services.knowledge_sync_service import run_scheduled_knowledge_syncs

    out = run_scheduled_knowledge_syncs(KILLED, client=_untouched_client())
    assert out == {"due_count": 0, "processed": 0, "outcomes": [], "skipped": "ingestion_disabled"}


def test_scheduled_knowledge_syncs_unchanged_when_off(monkeypatch) -> None:
    import app.services.knowledge_sync_service as svc

    monkeypatch.setattr(svc, "list_due_knowledge_connectors", lambda _client: [])
    out = svc.run_scheduled_knowledge_syncs(SimpleNamespace(disable_ingestion=False), client=MagicMock())
    assert out == {"due_count": 0, "processed": 0, "outcomes": []}


def test_manual_and_webhook_trigger_refused_before_any_row_is_written() -> None:
    from app.services.knowledge_sync_service import trigger_connector_knowledge_sync

    with pytest.raises(IngestionDisabledError):
        trigger_connector_knowledge_sync(_untouched_client(), KILLED, ORG, "c-1", actor_id="u-1")


def test_knowledge_sync_route_answers_503(monkeypatch) -> None:
    import app.routers.knowledge_sync as router

    monkeypatch.setattr(router, "shared_service_client", lambda *_a, **_k: _untouched_client())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(router._trigger_connector_sync_handler("c-1", ORG, "u-1", KILLED, full_sync=False))
    assert exc.value.status_code == 503


def test_connector_sync_alias_answers_503_not_502(monkeypatch) -> None:
    import app.routers.connectors as router

    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value
    chain.is_.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "c-1", "status": "active", "name": "n", "vendor": "notion", "type": "notion"}]
    )
    monkeypatch.setattr(router, "shared_service_client", lambda *_a, **_k: client)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            router.sync_connector_route_alias(
                "00000000-0000-4000-8000-000000000001", ({"user_id": "u-1"}, ORG), "production", KILLED
            )
        )
    assert exc.value.status_code == 503


@pytest.mark.parametrize(
    ("module", "fn", "body_cls"),
    [
        ("app.routers.notion_sync", "notion_sync_run", "NotionSyncRunRequest"),
        ("app.routers.confluence_sync", "confluence_sync_run", "ConfluenceSyncRunRequest"),
        ("app.routers.workday_sync", "workday_sync_run", "WorkdaySyncRunRequest"),
    ],
)
def test_direct_provider_sync_routes_answer_503(monkeypatch, module, fn, body_cls) -> None:
    import importlib

    router = importlib.import_module(module)
    monkeypatch.setattr(router, "shared_service_client", lambda *_a, **_k: _untouched_client())
    with pytest.raises(HTTPException) as exc:
        getattr(router, fn)("c-1", getattr(router, body_cls)(), ORG, {"user_id": "u-1"}, None, KILLED)
    assert exc.value.status_code == 503


# --------------------------------------------------------------------------- entity writer


def test_entity_writer_writes_nothing() -> None:
    from app.services.entity_writer import ProviderRecord, write_provider_records

    result = write_provider_records(
        _untouched_client(),
        KILLED,
        org_id=ORG,
        records=[ProviderRecord(system="hubspot", resource_type="company", resource_id="1", host="acme.com")],
    )
    assert result.as_dict()["created"] == 0 and result.as_dict()["joined"] == 0


def test_hubspot_company_feed_skips_before_calling_hubspot(monkeypatch) -> None:
    import app.connectors.hubspot as hs
    from app.services.hubspot_knowledge_sync_service import _write_company_entities

    def _boom(*_a, **_k):
        raise AssertionError("HubSpot must not be called while ingestion is disabled")

    monkeypatch.setattr(hs, "list_companies", _boom)
    out = _write_company_entities(_untouched_client(), KILLED, org_id=ORG, token="t")
    assert out == {"skipped": "ingestion_disabled"}


# --------------------------------------------------------------------------- observations


def test_observation_handler_skips_before_reading_the_provider() -> None:
    from app.services.customer_observation_feed import handle_customer_message

    event = {"org_id": ORG, "payload": {"system": "hubspot", "record_type": "email", "record_id": "9"}}
    assert handle_customer_message(_untouched_client(), event, KILLED) == {"skipped": "ingestion_disabled"}


def test_observe_customer_message_writes_nothing() -> None:
    from app.services.entity_observations import (
        CustomerMessage,
        observe_customer_message,
    )

    message = CustomerMessage(
        text="We are unhappy", source_system="hubspot", source_record_type="email",
        source_record_id="9", observed_at=NOW.isoformat(), author_email="a@customer.com",
    )
    out = asyncio.run(
        observe_customer_message(
            _untouched_client(), KILLED, org_id=ORG, entity_row_id="e1", message=message, org_domains={"us.com"}
        )
    )
    assert out == {"skipped": "ingestion_disabled"}


# --------------------------------------------------------------------------- behaviour signals


def test_behaviour_signal_pass_skips() -> None:
    from app.schedulers.entity_behavior_signals_scheduler import run_behavior_signals

    assert run_behavior_signals(_untouched_client(), now=NOW, settings=KILLED) == {}
