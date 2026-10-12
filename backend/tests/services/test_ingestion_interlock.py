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
    IngestionHeldError,
    ensure_existing_ingestion_allowed,
    existing_ingestion_hold_reason,
    ingestion_allowed_for_provider,
    ingestion_flag_on,
    ingestion_interlock_report,
    log_ingestion_interlock,
    missing_lifecycle_prerequisites,
    provider_lifecycle_supported,
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


# ------------------------------------------------------------------ providers without revoke


@pytest.mark.parametrize(
    "vendor", ["notion", "microsoft365", "zendesk", "confluence", "jira", "intercom", "workday", "", None, "unknown"]
)
def test_providers_without_revoke_are_not_lifecycle_supported(vendor):
    assert provider_lifecycle_supported(vendor) is False
    settings = SimpleNamespace(**ALL_INGESTION, **LIFECYCLE_ON)
    assert not any(ingestion_allowed_for_provider(settings, flag, vendor) for flag in INGESTION_FLAGS)


@pytest.mark.parametrize("vendor", ["hubspot", "salesforce", "slack", "gmail", "google_drive"])
def test_providers_with_revoke_are_supported_once_lifecycle_holds(vendor):
    assert provider_lifecycle_supported(vendor) is True
    on = SimpleNamespace(**ALL_INGESTION, **LIFECYCLE_ON)
    assert ingestion_allowed_for_provider(on, "rag_worker_pilot_enabled", vendor)
    assert not ingestion_allowed_for_provider(SimpleNamespace(**ALL_INGESTION), "rag_worker_pilot_enabled", vendor)


# ------------------------------------------------------------------ existing ingestion (owner switch)


def test_existing_ingestion_runs_as_before_by_default():
    # Default settings: lifecycle is not enforced, yet existing knowledge syncs are not held.
    assert Settings().existing_ingestion_requires_lifecycle is False
    for vendor in (None, "notion", "hubspot", "zendesk"):
        assert existing_ingestion_hold_reason(Settings(), vendor) is None
    ensure_existing_ingestion_allowed(Settings(), "notion")


def test_owner_switch_holds_existing_ingestion_until_lifecycle_and_revoke():
    gated = SimpleNamespace(existing_ingestion_requires_lifecycle=True)
    assert existing_ingestion_hold_reason(gated).startswith("lifecycle_prerequisites_missing:")
    with pytest.raises(IngestionHeldError):
        ensure_existing_ingestion_allowed(gated, "hubspot")
    ready = SimpleNamespace(existing_ingestion_requires_lifecycle=True, **LIFECYCLE_ON)
    assert existing_ingestion_hold_reason(ready) is None
    assert existing_ingestion_hold_reason(ready, "hubspot") is None
    assert existing_ingestion_hold_reason(ready, "notion") == "provider_revoke_not_supported:notion"
    with pytest.raises(IngestionHeldError):
        ensure_existing_ingestion_allowed(ready, "zendesk")
    ensure_existing_ingestion_allowed(ready, "hubspot")


def test_report_shows_ungated_existing_ingestion_and_limitations():
    report = ingestion_interlock_report(Settings())
    assert report["lifecycle_ready"] is False
    assert report["missing"] == missing_lifecycle_prerequisites(Settings())
    assert report["prerequisites"]["source_purge_dry_run"] == {"required": False, "actual": True, "ok": False}
    assert all(v == {"requested": False, "effective": False} for v in report["new_ingestion"].values())
    assert report["existing_ingestion"]["requires_lifecycle"] is False
    assert set(report["existing_ingestion"]["knowledge_sync"].values()) == {"running_ungated"}
    assert report["existing_ingestion"]["standalone_worker"] == "running_ungated"
    assert report["providers_without_revoke"] == ["confluence", "notion", "workday", "zendesk"]
    text = " ".join(report["limitations"])
    assert "configuration flags only" in text and "entity_observations" in text and "intercom" in text


def test_report_with_owner_switch_and_lifecycle_on():
    s = SimpleNamespace(existing_ingestion_requires_lifecycle=True, entity_writer_enabled=True, **LIFECYCLE_ON)
    report = ingestion_interlock_report(s)
    assert report["lifecycle_ready"] is True
    assert report["new_ingestion"]["entity_writer_enabled"] == {"requested": True, "effective": True}
    sync = report["existing_ingestion"]["knowledge_sync"]
    assert sync["hubspot"] == "allowed"
    assert sync["notion"] == "held:provider_revoke_not_supported:notion"
    assert report["existing_ingestion"]["standalone_worker"] == "allowed"


def test_startup_log_names_ungated_existing_ingestion(caplog):
    with caplog.at_level(logging.WARNING):
        log_ingestion_interlock(Settings())
    assert "existing_ingestion=ungated" in caplog.text
    assert "EXISTING_INGESTION_REQUIRES_LIFECYCLE=true" in caplog.text
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        log_ingestion_interlock(SimpleNamespace(existing_ingestion_requires_lifecycle=True))
    assert "existing_ingestion=ungated" not in caplog.text


# ------------------------------------------------------------------ pilot-scoped work


class _JobClient:
    """Answers the rag_sources type lookup; records ingest-job releases."""

    def __init__(self, source_type: str) -> None:
        self.source_type = source_type
        self.updates: list[dict] = []

    def table(self, name):
        client = self

        class _Q:
            def select(self, *_a):
                return self

            def eq(self, *_a):
                return self

            def limit(self, *_a):
                return self

            def update(self, payload):
                assert name == "rag_ingest_jobs"
                client.updates.append(payload)
                return self

            def execute(self):
                return SimpleNamespace(data=[{"type": client.source_type}])

        return _Q()


PILOT_ORG = "11111111-1111-4111-8111-111111111111"
OTHER_ORG = "22222222-2222-4222-8222-222222222222"
RELEASED = {"status": "queued", "worker_id": None, "heartbeat_at": None}


def _pilot_settings(**kw):
    base = {"rag_worker_pilot_enabled": True, "rag_worker_pilot_org_ids": PILOT_ORG, "disable_ingestion": False}
    return SimpleNamespace(**{**base, **kw})


@pytest.mark.parametrize(
    ("settings", "source_type", "opted_in", "expected"),
    [
        (_pilot_settings(), "hubspot", True, "lifecycle_interlock"),
        (_pilot_settings(rag_worker_pilot_enabled=False, **LIFECYCLE_ON), "hubspot", True, "lifecycle_interlock"),
        (_pilot_settings(**LIFECYCLE_ON), "notion", True, "provider_lifecycle_unsupported"),
        (_pilot_settings(**LIFECYCLE_ON), "zendesk", True, "provider_lifecycle_unsupported"),
        (_pilot_settings(**LIFECYCLE_ON), "hubspot", False, "customer_context_not_opted_in"),
        (_pilot_settings(**LIFECYCLE_ON), "hubspot", True, None),
    ],
)
def test_pilot_job_hold_reason(monkeypatch, settings, source_type, opted_in, expected):
    monkeypatch.setattr("app.services.source_governance.customer_context_allowed_for_org", lambda *a: opted_in)
    job = {"id": "j1", "org_id": PILOT_ORG, "source_id": "s1", "worker_id": "w"}
    assert pilot.pilot_job_hold_reason(settings, _JobClient(source_type), job) == expected


def test_pilot_tick_releases_jobs_of_providers_without_revoke(monkeypatch):
    from app.rag import worker

    jobs = [{"id": "j1", "org_id": PILOT_ORG, "source_id": "s1", "worker_id": "w"}]

    class _Client(_JobClient):
        def rpc(self, _name, _params):
            data = [jobs.pop(0)] if jobs else []
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=data))

    processed: list[str] = []
    monkeypatch.setattr(worker, "process_job", lambda s, c, job: processed.append(job["id"]))
    monkeypatch.setattr("app.services.source_governance.customer_context_allowed_for_org", lambda *a: True)
    client = _Client("notion")
    out = pilot.run_pilot_tick(_pilot_settings(**LIFECYCLE_ON), client, "w")
    assert processed == [] and out == {"processed": 0, "released": 1}
    assert client.updates == [RELEASED]


# ------------------------------------------------------------------ standalone worker


class _WorkerClient(_JobClient):
    def __init__(self, source_type: str, job: dict | None) -> None:
        super().__init__(source_type)
        self.job = job
        self.claims = 0

    def rpc(self, name, _params):
        assert name == "claim_rag_ingest_job"
        self.claims += 1
        job, self.job = self.job, None
        return SimpleNamespace(execute=lambda: SimpleNamespace(data=[job] if job else []))


@pytest.fixture
def processed(monkeypatch):
    from app.rag import worker

    seen: list[str] = []
    monkeypatch.setattr(worker, "process_job", lambda s, c, job: seen.append(job["id"]))
    monkeypatch.setattr("app.services.source_governance.customer_context_allowed_for_org", lambda *a: True)
    return seen


def _job(org: str = PILOT_ORG, job_id: str = "j1") -> dict:
    return {"id": job_id, "org_id": org, "source_id": "s1", "worker_id": "w"}


def test_standalone_worker_holds_pilot_org_jobs_without_lifecycle(processed):
    from app.rag.worker import run_worker_once

    client = _WorkerClient("hubspot", _job())
    assert run_worker_once(_pilot_settings(), client, "w") == "released"
    assert processed == []
    assert client.updates == [RELEASED]


def test_standalone_worker_holds_pilot_org_jobs_of_providers_without_revoke(processed):
    from app.rag.worker import run_worker_once

    client = _WorkerClient("confluence", _job())
    assert run_worker_once(_pilot_settings(**LIFECYCLE_ON), client, "w") == "released"
    assert processed == [] and client.updates == [RELEASED]


def test_standalone_worker_indexes_pilot_org_jobs_once_lifecycle_holds(processed):
    from app.rag.worker import run_worker_once

    client = _WorkerClient("hubspot", _job())
    assert run_worker_once(_pilot_settings(**LIFECYCLE_ON), client, "w") == "processed"
    assert processed == ["j1"] and client.updates == []


def test_standalone_worker_unchanged_for_other_orgs_by_default(processed):
    from app.rag.worker import run_worker_once

    # Not a pilot org and the owner switch is off: indexed exactly as before.
    client = _WorkerClient("notion", _job(OTHER_ORG, "j2"))
    assert run_worker_once(_pilot_settings(), client, "w") == "processed"
    assert run_worker_once(_pilot_settings(), client, "w") == "idle"
    assert processed == ["j2"]


def test_standalone_worker_honours_disable_ingestion_and_owner_switch(processed):
    from app.rag.worker import run_worker_once

    client = _WorkerClient("hubspot", _job(OTHER_ORG, "j3"))
    assert run_worker_once(_pilot_settings(disable_ingestion=True), client, "w") == "disabled"
    assert run_worker_once(_pilot_settings(existing_ingestion_requires_lifecycle=True), client, "w") == "held"
    assert client.claims == 0
    ready = _pilot_settings(existing_ingestion_requires_lifecycle=True, **LIFECYCLE_ON)
    assert run_worker_once(ready, _WorkerClient("notion", _job(OTHER_ORG, "j3")), "w") == "released"
    assert run_worker_once(ready, _WorkerClient("hubspot", _job(OTHER_ORG, "j3")), "w") == "processed"
    assert processed == ["j3"]
