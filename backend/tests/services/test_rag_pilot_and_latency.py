"""Phase 2D: indexing pilot bounds, checksum skip, latency baseline gate."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.rag import worker
from app.schedulers import rag_ingest_pilot_scheduler as pilot
from app.services import latency_baseline as lb
from app.services.ingestion_interlock import LIFECYCLE_PREREQUISITES

LIFECYCLE_ON = dict(LIFECYCLE_PREREQUISITES)
# Configuration is what these tests vary; runtime lifecycle evidence is present
# (healthy relay in this process). Runtime-state cases: test_lifecycle_runtime.py.
pytestmark = pytest.mark.usefixtures("lifecycle_runtime_ready")

ORG = "11111111-1111-4111-8111-111111111111"
ORG2 = "22222222-2222-4222-8222-222222222222"


# ------------------------------------------------------------------ pilot


def test_pilot_org_ids_parse_only_uuids():
    s = SimpleNamespace(rag_worker_pilot_org_ids=f" {ORG.upper()}, nope, {ORG2},")
    assert pilot.pilot_org_ids(s) == [ORG, ORG2]
    assert pilot.pilot_org_ids(SimpleNamespace()) == []


def test_pilot_off_by_default_and_without_orgs(monkeypatch):
    monkeypatch.setattr(pilot, "get_settings", lambda: SimpleNamespace())
    assert pilot.start_rag_ingest_pilot_scheduler() is None
    monkeypatch.setattr(pilot, "get_settings", lambda: SimpleNamespace(rag_worker_pilot_enabled=True, **LIFECYCLE_ON))
    assert pilot.start_rag_ingest_pilot_scheduler() is None


class _PilotClient:
    def __init__(self, jobs: list[dict[str, Any]]) -> None:
        self.jobs = jobs
        self.claims: list[dict[str, Any]] = []
        self.updates: list[dict[str, Any]] = []
        self.source_type = "hubspot"

    def rpc(self, name, params):
        assert name == "claim_rag_ingest_job_for_orgs"
        self.claims.append(params)

        def execute():
            for i, j in enumerate(self.jobs):
                if j["org_id"] in params["p_org_ids"]:
                    return SimpleNamespace(data=[self.jobs.pop(i)])
            return SimpleNamespace(data=[])

        return SimpleNamespace(execute=execute)

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
                client.updates.append(payload)
                return self

            def execute(self):
                return SimpleNamespace(data=[{"type": client.source_type}])

        return _Q()


def test_pilot_processes_opted_in_orgs_and_releases_others(monkeypatch):
    jobs = [
        {"id": "j1", "org_id": ORG, "source_id": "s1", "worker_id": "w"},
        {"id": "j2", "org_id": ORG2, "source_id": "s2", "worker_id": "w"},
        {"id": "j3", "org_id": ORG, "source_id": "s1", "worker_id": "w"},
    ]
    client = _PilotClient(jobs)
    processed: list[str] = []
    monkeypatch.setattr(worker, "process_job", lambda s, c, job: processed.append(job["id"]))
    monkeypatch.setattr(
        "app.services.source_governance.customer_context_allowed_for_org",
        lambda c, org_id, vendor: org_id == ORG and vendor == "hubspot",
    )
    settings = SimpleNamespace(
        rag_worker_pilot_enabled=True,
        rag_worker_pilot_org_ids=f"{ORG},{ORG2}",
        rag_worker_pilot_max_jobs_per_tick=10,
        **LIFECYCLE_ON,
    )
    out = pilot.run_pilot_tick(settings, client, "w")
    assert processed == ["j1", "j3"]
    assert out == {"processed": 2, "released": 1}
    assert client.updates == [{"status": "queued", "worker_id": None, "heartbeat_at": None}]
    # After the release, ORG2 is no longer asked for in this tick.
    assert all(ORG2 not in c["p_org_ids"] for c in client.claims[2:])


def test_pilot_respects_per_tick_limit(monkeypatch):
    client = _PilotClient([{"id": f"j{i}", "org_id": ORG, "source_id": "s"} for i in range(9)])
    monkeypatch.setattr(worker, "process_job", lambda *a: None)
    monkeypatch.setattr("app.services.source_governance.customer_context_allowed_for_org", lambda *a: True)
    out = pilot.run_pilot_tick(
        SimpleNamespace(
            rag_worker_pilot_enabled=True,
            rag_worker_pilot_org_ids=ORG,
            rag_worker_pilot_max_jobs_per_tick=3,
            **LIFECYCLE_ON,
        ),
        client,
        "w",
    )
    assert out["processed"] == 3 and len(client.jobs) == 6


# ------------------------------------------------------------------ checksum skip


class _DocClient:
    def __init__(self, active_meta: dict[str, Any] | None) -> None:
        self.active_meta = active_meta
        self.finalized: list[dict[str, Any]] = []

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
                if name == "rag_ingest_jobs":
                    client.finalized.append(payload)
                return self

            def execute(self):
                if name == "rag_documents" and client.active_meta is not None:
                    return SimpleNamespace(data=[{"id": "doc-active", "metadata": client.active_meta}])
                return SimpleNamespace(data=[])

        return _Q()


def _job() -> dict[str, Any]:
    return {
        "id": "j1",
        "org_id": ORG,
        "source_id": "s1",
        "external_id": "notion:page:p1",
        "request_payload": {"title": "Runbook", "text": "Step one. Step two."},
    }


def _settings(**kw) -> SimpleNamespace:
    base: dict[str, Any] = {"embedding_model": "m", "openai_embedding_dimension": 1536}
    base.update(kw)
    return SimpleNamespace(**base)


def test_checksum_is_stable_and_content_sensitive():
    a = worker.content_checksum("T", ["x", "y"])
    assert a == worker.content_checksum("T", ["x", "y"])
    assert a != worker.content_checksum("T", ["xy"])
    assert a != worker.content_checksum("U", ["x", "y"])


def test_unchanged_document_is_skipped_when_enabled(monkeypatch):
    chunks = worker.chunk_document_text("Step one. Step two.", settings=_settings(), chunking={})
    sha = worker.content_checksum("Runbook", chunks)
    client = _DocClient({"content_sha256": sha})
    monkeypatch.setattr(worker, "upsert_document", lambda *a, **k: pytest.fail("must not re-ingest"))
    worker.process_job(_settings(rag_ingest_checksum_skip_enabled=True), client, _job())
    assert client.finalized[0]["status"] == "completed"
    assert client.finalized[0]["document_id"] == "doc-active"


@pytest.mark.parametrize(
    ("flag", "meta"),
    [(False, "same"), (True, {"content_sha256": "different"}), (True, None)],
)
def test_changed_or_flag_off_reingests_with_checksum(monkeypatch, flag, meta):
    chunks = worker.chunk_document_text("Step one. Step two.", settings=_settings(), chunking={})
    sha = worker.content_checksum("Runbook", chunks)
    client = _DocClient({"content_sha256": sha} if meta == "same" else meta)
    stored: list[dict[str, Any]] = []

    def upsert(*_a, **k):
        stored.append(k["metadata"])
        raise ValueError("stop here")

    monkeypatch.setattr(worker, "upsert_document", upsert)
    monkeypatch.setattr(worker, "cleanup_document_version", lambda *a: None)
    worker.process_job(_settings(rag_ingest_checksum_skip_enabled=flag), client, _job())
    assert stored == [{"content_sha256": sha}]


# ------------------------------------------------------------------ latency baseline


def _text(ms):
    return {"total_ms": ms}


def _voice(ms, key="speech_end_to_playback_ms"):
    return {"voice_transport": "pipecat_duplex", "stage_durations_ms": {key: ms}}


def test_summary_splits_surfaces_and_requires_samples():
    payloads = [_text(1000 + i * 10) for i in range(60)] + [_voice(2000) for _ in range(10)]
    payloads += [_voice(1500, "speech_end_to_server_audio_ms"), {"total_ms": 0}, "junk"]
    s = lb.summarize(payloads)
    assert s["text"]["n"] == 60 and s["text"]["p50"] == 1290 and s["text"]["p95"] == 1560
    assert s["voice"] == {"n": 11, "p50": None, "p95": None}


def test_compare_flags_regression_beyond_threshold():
    base = {"text": {"p50": 1000, "p95": 3000}, "voice": {"p50": 2000, "p95": None}}
    cur = {"text": {"p50": 1050, "p95": 3600}, "voice": {"p50": 2100, "p95": 5000}}
    rows = {(r["surface"], r["pct"]): r for r in lb.compare(cur, base, max_regression_pct=10)}
    assert rows[("text", "p50")]["verdict"] == "ok"
    assert rows[("text", "p95")]["verdict"] == "regressed" and rows[("text", "p95")]["change_pct"] == 20.0
    assert rows[("voice", "p50")]["verdict"] == "ok"
    assert rows[("voice", "p95")]["verdict"] == "insufficient"


def test_script_capture_and_check(tmp_path):
    import importlib.util
    import json
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "latency_baseline_script", Path(__file__).resolve().parents[2] / "scripts" / "latency_baseline.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    traces = tmp_path / "t.jsonl"
    traces.write_text("\n".join(json.dumps(_text(1000)) for _ in range(60)))
    out = tmp_path / "b.json"
    assert mod.main(["capture", "--input", str(traces), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["text"]["p50"] == 1000
    slow = tmp_path / "s.jsonl"
    slow.write_text("\n".join(json.dumps(_text(1500)) for _ in range(60)))
    assert mod.main(["check", "--input", str(slow), "--baseline", str(out)]) == 1
    assert mod.main(["check", "--input", str(traces), "--baseline", str(out)]) == 0
