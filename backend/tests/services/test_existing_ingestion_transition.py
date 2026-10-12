"""What flipping EXISTING_INGESTION_REQUIRES_LIFECYCLE from false to true does.

One in-memory tenant state (connectors due for scheduled sync, queued RAG ingest
jobs) is driven through the transition the owner would make:

  false (today) -> true, lifecycle not ready -> true, ready -> back to false

and the tests pin down what happens to scheduled syncs and queued jobs at each
step: nothing is deleted or failed, held work stays queued/due and resumes when
the hold lifts, and one hazard (head-of-line blocking of the global ingest queue)
that must be handled before the switch is turned on in production.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from app.rag import worker
from app.services import knowledge_sync_service as ks
from app.services.ingestion_interlock import LIFECYCLE_PREREQUISITES

ORG_A = "11111111-1111-4111-8111-111111111111"
ORG_B = "22222222-2222-4222-8222-222222222222"
OLD = (datetime.now(UTC) - timedelta(days=2)).isoformat()

OFF = SimpleNamespace(existing_ingestion_requires_lifecycle=False, disable_ingestion=False)
ON_NOT_CONFIGURED = SimpleNamespace(existing_ingestion_requires_lifecycle=True, disable_ingestion=False)
ON_CONFIGURED = SimpleNamespace(
    existing_ingestion_requires_lifecycle=True, disable_ingestion=False, **dict(LIFECYCLE_PREREQUISITES)
)


class _Store:
    """Just enough of PostgREST over in-memory rows for the sync scheduler and worker."""

    def __init__(self) -> None:
        self.rows: dict[str, list[dict[str, Any]]] = {
            "connectors": [
                {
                    "id": "c-notion", "org_id": ORG_A, "type": "notion", "vendor": "notion",
                    "status": "active", "deleted_at": None, "environment": "production",
                    "sync_frequency": "1h", "last_sync_at": OLD,
                    "config": {"notion_sync_targets": [{"id": "page-1"}]},
                },
                {
                    "id": "c-hubspot", "org_id": ORG_B, "type": "hubspot", "vendor": "hubspot",
                    "status": "active", "deleted_at": None, "environment": "production",
                    "sync_frequency": "1h", "last_sync_at": OLD, "config": {},
                },
            ],
            "rag_sources": [
                {"id": "s-notion", "org_id": ORG_A, "type": "notion"},
                {"id": "s-hubspot", "org_id": ORG_B, "type": "hubspot"},
            ],
            "rag_ingest_jobs": [
                # Oldest first: an Org A Notion job sits at the head of the global queue.
                {"id": "j-notion", "org_id": ORG_A, "source_id": "s-notion", "status": "queued",
                 "worker_id": None, "created_at": "2026-10-01T00:00:00+00:00"},
                {"id": "j-hubspot", "org_id": ORG_B, "source_id": "s-hubspot", "status": "queued",
                 "worker_id": None, "created_at": "2026-10-01T00:00:01+00:00"},
            ],
        }
        self.claims: list[str] = []
        self.sync_jobs: list[dict[str, Any]] = []

    # -- PostgREST surface
    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def rpc(self, name: str, params: dict[str, Any]) -> SimpleNamespace:
        assert name == "claim_rag_ingest_job", name

        def execute() -> SimpleNamespace:
            queued = sorted(
                (j for j in self.rows["rag_ingest_jobs"] if j["status"] == "queued"), key=lambda j: j["created_at"]
            )
            if not queued:
                return SimpleNamespace(data=[])
            job = queued[0]
            job.update(status="running", worker_id=params["p_worker_id"])
            self.claims.append(job["id"])
            return SimpleNamespace(data=[dict(job)])

        return SimpleNamespace(execute=execute)

    # -- helpers
    def job(self, job_id: str) -> dict[str, Any]:
        return next(j for j in self.rows["rag_ingest_jobs"] if j["id"] == job_id)

    def connector(self, cid: str) -> dict[str, Any]:
        return next(c for c in self.rows["connectors"] if c["id"] == cid)


class _Query:
    def __init__(self, store: _Store, name: str) -> None:
        self.store = store
        self.name = name
        self.preds: list = []
        self.patch: dict[str, Any] | None = None

    def select(self, *_a: Any) -> _Query:
        return self

    def eq(self, col: str, val: Any) -> _Query:
        self.preds.append(lambda r, c=col, v=val: str(r.get(c)) == str(v))
        return self

    def in_(self, col: str, vals: list[Any]) -> _Query:
        self.preds.append(lambda r, c=col, v=tuple(vals): r.get(c) in v)
        return self

    def is_(self, col: str, val: str) -> _Query:
        assert val == "null"
        self.preds.append(lambda r, c=col: r.get(c) is None)
        return self

    def limit(self, _n: int) -> _Query:
        return self

    def update(self, patch: dict[str, Any]) -> _Query:
        self.patch = patch
        return self

    def execute(self) -> SimpleNamespace:
        rows = [r for r in self.store.rows[self.name] if all(p(r) for p in self.preds)]
        if self.patch is not None:
            for r in rows:
                r.update(self.patch)
        return SimpleNamespace(data=[dict(r) for r in rows])


def _scheduled(store: _Store, settings: Any) -> dict[str, Any]:
    def create_job(_client, **kw):
        row = {"id": f"ksj-{len(store.sync_jobs)}", **kw}
        store.sync_jobs.append(row)
        return row

    def execute_job(_client, _settings, job, connector, **_kw):
        store.connector(connector["id"])["last_sync_at"] = datetime.now(UTC).isoformat()
        return {"pages_synced": 1, "jobs_queued": 0}

    with patch.object(ks, "create_knowledge_sync_job", side_effect=create_job), patch.object(
        ks, "execute_knowledge_sync_job", side_effect=execute_job
    ):
        return ks.run_scheduled_knowledge_syncs(settings, client=store)


def _worker_poll(store: _Store, settings: Any) -> str:
    def process(_settings, _client, job):
        store.job(job["id"]).update(status="completed")

    with patch.object(worker, "process_job", side_effect=process):
        return worker.run_worker_once(settings, store, "w-1")


def _due(store: _Store) -> set[str]:
    return {c["id"] for c in ks.list_due_knowledge_connectors(store)}


# ------------------------------------------------------------------ false (today)


def test_switch_off_everything_runs_as_today():
    store = _Store()
    summary = _scheduled(store, OFF)
    assert summary["processed"] == 2 and summary.get("held", 0) == 0
    assert _due(store) == set()
    assert _worker_poll(store, OFF) == "processed"
    assert _worker_poll(store, OFF) == "processed"
    assert {j["status"] for j in store.rows["rag_ingest_jobs"]} == {"completed"}


# ------------------------------------------------------------------ true, lifecycle not ready


def test_switch_on_without_lifecycle_holds_everything_and_loses_nothing():
    for settings in (ON_NOT_CONFIGURED, ON_CONFIGURED):  # config missing / runtime evidence missing
        store = _Store()
        summary = _scheduled(store, settings)
        assert summary["processed"] == 0 and summary["held_reason"]
        # No sync job row written, last_sync_at untouched: both connectors stay due.
        assert store.sync_jobs == []
        assert _due(store) == {"c-notion", "c-hubspot"}
        # The standalone worker does not even claim: queued jobs stay queued, unowned.
        assert _worker_poll(store, settings) == "held"
        assert store.claims == []
        assert [(j["status"], j["worker_id"]) for j in store.rows["rag_ingest_jobs"]] == [
            ("queued", None),
            ("queued", None),
        ]


# ------------------------------------------------------------------ true, lifecycle ready


def test_switch_on_and_ready_runs_revocable_providers_and_holds_the_rest(lifecycle_runtime_ready):
    store = _Store()
    summary = _scheduled(store, ON_CONFIGURED)
    assert summary["processed"] == 1 and summary["held"] == 1
    held = [o for o in summary["outcomes"] if o["status"] == "held"]
    assert held == [
        {"connector_id": "c-notion", "status": "held", "reason": "provider_revoke_not_supported:notion"}
    ]
    assert [j["connector_id"] for j in store.sync_jobs] == ["c-hubspot"]
    # The held Notion connector stays due and is retried (and held) every scheduler tick.
    assert _due(store) == {"c-notion"}


def test_switch_on_and_ready_head_of_line_blocks_the_global_queue(lifecycle_runtime_ready):
    """Hazard: the oldest queued job is a Notion job, which is released back to the queue
    and reclaimed on every poll. Org B's HubSpot job behind it is never processed.

    claim_rag_ingest_job is global and oldest-first, so one held provider anywhere
    stalls the standalone worker for every org. Must be resolved (or the worker not run)
    before EXISTING_INGESTION_REQUIRES_LIFECYCLE is turned on.
    """
    store = _Store()
    outcomes = [_worker_poll(store, ON_CONFIGURED) for _ in range(3)]
    assert outcomes == ["released", "released", "released"]
    assert store.claims == ["j-notion", "j-notion", "j-notion"]
    assert store.job("j-notion")["status"] == "queued" and store.job("j-notion")["worker_id"] is None
    assert store.job("j-hubspot")["status"] == "queued"


# ------------------------------------------------------------------ back to false


def test_switching_back_off_resumes_held_work(lifecycle_runtime_ready):
    store = _Store()
    _scheduled(store, ON_CONFIGURED)
    _worker_poll(store, ON_CONFIGURED)
    assert _due(store) == {"c-notion"}
    summary = _scheduled(store, OFF)
    assert summary["processed"] == 1 and [o["connector_id"] for o in summary["outcomes"]] == ["c-notion"]
    assert _worker_poll(store, OFF) == "processed"
    assert _worker_poll(store, OFF) == "processed"
    assert {j["status"] for j in store.rows["rag_ingest_jobs"]} == {"completed"}


def test_disable_ingestion_wins_over_every_switch_state(lifecycle_runtime_ready):
    for settings in (OFF, ON_NOT_CONFIGURED, ON_CONFIGURED):
        store = _Store()
        disabled = SimpleNamespace(**{**vars(settings), "disable_ingestion": True})
        assert _worker_poll(store, disabled) == "disabled"
        assert store.claims == []
