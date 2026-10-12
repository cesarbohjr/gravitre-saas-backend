"""Customer ingestion flags do nothing until source lifecycle is enforced."""
from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.schedulers import entity_behavior_signals_scheduler as signals
from app.schedulers import rag_ingest_pilot_scheduler as pilot
from app.services import entity_observations, entity_writer
from app.services.ingestion_interlock import (
    INGESTION_FLAGS,
    LIFECYCLE_PREREQUISITES,
    ingestion_flag_on,
    log_ingestion_interlock,
    missing_lifecycle_prerequisites,
)

LIFECYCLE_ON = dict(LIFECYCLE_PREREQUISITES)
ALL_INGESTION = {flag: True for flag in INGESTION_FLAGS}


def test_defaults_miss_every_prerequisite():
    missing = missing_lifecycle_prerequisites(Settings())
    assert missing == [
        "DOMAIN_EVENT_RELAY_ENABLED=true",
        "SOURCE_DELETION_PROPAGATION_ENABLED=true",
        "CONNECTOR_PROVIDER_REVOKE_ON_DISCONNECT=true",
        "SOURCE_PURGE_DRY_RUN=false",
    ]


@pytest.mark.parametrize("name", [name for name, _ in LIFECYCLE_PREREQUISITES])
def test_each_prerequisite_alone_holds_ingestion_back(name):
    settings = SimpleNamespace(**ALL_INGESTION, **{**LIFECYCLE_ON, name: not LIFECYCLE_ON[name]})
    assert not any(ingestion_flag_on(settings, flag) for flag in INGESTION_FLAGS)
    assert not entity_observations.observations_enabled(settings)
    assert not entity_writer.writer_enabled(settings)


def test_flags_work_once_lifecycle_holds():
    settings = SimpleNamespace(**ALL_INGESTION, **LIFECYCLE_ON)
    assert all(ingestion_flag_on(settings, flag) for flag in INGESTION_FLAGS)
    assert entity_observations.observations_enabled(settings)
    assert entity_writer.writer_enabled(settings)
    assert not ingestion_flag_on(SimpleNamespace(**LIFECYCLE_ON), "entity_writer_enabled")


def test_schedulers_stay_off_without_lifecycle(monkeypatch):
    held = SimpleNamespace(**ALL_INGESTION, rag_worker_pilot_org_ids="11111111-1111-4111-8111-111111111111")
    monkeypatch.setattr(pilot, "get_settings", lambda: held)
    monkeypatch.setattr(signals, "get_settings", lambda: held)
    assert pilot.start_rag_ingest_pilot_scheduler() is None
    assert signals.start_entity_behavior_signals_scheduler() is None


def test_startup_log_names_held_flags_and_missing_prerequisites(caplog):
    settings = SimpleNamespace(entity_observations_enabled=True)
    with caplog.at_level(logging.WARNING):
        held = log_ingestion_interlock(settings)
    assert held == ["entity_observations_enabled"]
    assert "ENTITY_OBSERVATIONS_ENABLED" in caplog.text
    assert "SOURCE_PURGE_DRY_RUN=false" in caplog.text
    assert log_ingestion_interlock(Settings()) == []
    assert log_ingestion_interlock(SimpleNamespace(entity_observations_enabled=True, **LIFECYCLE_ON)) == []
