"""Phase 2A outbox migration against a real, throwaway PostgreSQL cluster.

Starts a private cluster (initdb + pg_ctl on a unix socket in a temp dir), creates
the Supabase roles and the minimal shapes of the tables the triggers attach to,
applies ``20261011220000_domain_event_outbox.sql`` unchanged, and checks the
properties the outbox relies on: same-transaction writes, idempotency, RLS,
SKIP LOCKED claiming across concurrent sessions, leases, retries and
dead-lettering. Skips when no PostgreSQL server binaries are installed.
"""
from __future__ import annotations

import concurrent.futures
import glob
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MIGRATION = REPO_ROOT / "supabase" / "migrations" / "20261011220000_domain_event_outbox.sql"

ORG = "11111111-1111-4111-8111-111111111111"
USER = "22222222-2222-4222-8222-222222222222"


def _pg_bin() -> Path | None:
    env = os.environ.get("GRAVITRE_PG_BIN")
    candidates = [env] if env else []
    candidates += sorted(glob.glob("/usr/lib/postgresql/*/bin"), reverse=True)
    for c in candidates:
        if c and (Path(c) / "initdb").exists() and (Path(c) / "pg_ctl").exists():
            return Path(c)
    return None


PG_BIN = _pg_bin()
pytestmark = pytest.mark.skipif(PG_BIN is None, reason="PostgreSQL server binaries not installed")


BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE TABLE auth.users (id uuid PRIMARY KEY);
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.workflow_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  workflow_id uuid,
  status text NOT NULL CHECK (status IN ('running','completed','failed','cancelled',
    'pending_approval','awaiting_approval','paused','partial_success','flagged_for_review',
    'verification_inconclusive')),
  parameters jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE TABLE public.connectors (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  type text NOT NULL,
  status text NOT NULL DEFAULT 'connected',
  deleted_at timestamptz
);
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workflow_runs, public.connectors
  TO authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
INSERT INTO public.organizations VALUES ('{ORG}');
INSERT INTO auth.users VALUES ('{USER}');
"""


class _Pg:
    def __init__(self, root: Path, run_as: list[str]) -> None:
        self.root = root
        self.data = root / "data"
        self.sock = root / "sock"
        self.run_as = run_as
        self.port = "54329"

    def _cmd(self, binary: str, *args: str) -> list[str]:
        return [*self.run_as, str(PG_BIN / binary), *args]

    def start(self) -> None:
        self.sock.mkdir()
        if self.run_as:
            shutil.chown(self.sock, "postgres", "postgres")
        subprocess.run(
            self._cmd("initdb", "-D", str(self.data), "-A", "trust", "-U", "postgres", "--no-sync"),
            check=True,
            capture_output=True,
        )
        opts = f"-k {self.sock} -p {self.port} -c listen_addresses='' -c fsync=off"
        subprocess.run(
            self._cmd("pg_ctl", "-D", str(self.data), "-o", opts, "-w", "-l", str(self.root / "log"), "start"),
            check=True,
            capture_output=True,
        )

    def stop(self) -> None:
        subprocess.run(
            self._cmd("pg_ctl", "-D", str(self.data), "-m", "immediate", "stop"),
            capture_output=True,
            check=False,
        )

    def psql(self, sql: str, *, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                str(PG_BIN / "psql"),
                "-h", str(self.sock), "-p", self.port, "-U", "postgres", "-d", "postgres",
                "-X", "-q", "-At", "-v", "ON_ERROR_STOP=1",
            ],
            input=sql,
            text=True,
            capture_output=True,
            check=check,
        )

    def value(self, sql: str) -> str:
        return self.psql(sql).stdout.strip()


@pytest.fixture(scope="module")
def pg():
    root = Path(tempfile.mkdtemp(prefix="gravitre-pg-"))
    run_as: list[str] = []
    if os.geteuid() == 0:
        if shutil.which("runuser") is None:
            pytest.skip("running as root without runuser")
        shutil.chown(root, "postgres", "postgres")
        os.chmod(root, 0o777)
        run_as = ["runuser", "-u", "postgres", "--"]
    server = _Pg(root, run_as)
    server.start()
    try:
        server.psql(BOOTSTRAP_SQL)
        server.psql(MIGRATION.read_text())
        yield server
    finally:
        server.stop()
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("TRUNCATE public.domain_event_outbox; DELETE FROM public.workflow_runs; DELETE FROM public.connectors;")
    yield


def _new_run(pg, status: str = "running") -> str:
    return pg.value(
        f"INSERT INTO public.workflow_runs (org_id, status) VALUES ('{ORG}', '{status}') RETURNING id;"
    )


def _events(pg, event_type: str | None = None) -> list[dict]:
    where = f"WHERE event_type = '{event_type}'" if event_type else ""
    out = pg.value(f"SELECT coalesce(json_agg(o ORDER BY id), '[]') FROM public.domain_event_outbox o {where};")
    return json.loads(out)


# ---------------------------------------------------------------- producers


def test_migration_is_idempotent(pg):
    pg.psql(MIGRATION.read_text())  # second apply must not fail
    assert pg.value("SELECT count(*) FROM pg_trigger WHERE tgname = 'workflow_runs_emit_terminal_event';") == "1"


def test_terminal_transition_emits_one_event(pg):
    run_id = _new_run(pg)
    assert _events(pg) == []
    pg.psql(f"UPDATE public.workflow_runs SET status = 'completed', completed_at = now() WHERE id = '{run_id}';")
    events = _events(pg)
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "execution.outcome_finalized"
    assert ev["aggregate_id"] == run_id
    assert ev["idempotency_key"] == f"{run_id}:completed"
    assert ev["payload"]["previous_status"] == "running"
    assert ev["status"] == "pending" and ev["criticality"] == "critical"


def test_rolled_back_change_leaves_no_event(pg):
    run_id = _new_run(pg)
    pg.psql(f"BEGIN; UPDATE public.workflow_runs SET status = 'failed' WHERE id = '{run_id}'; ROLLBACK;")
    assert _events(pg) == []
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id = '{run_id}';") == "running"


def test_event_commits_with_the_change_in_one_transaction(pg):
    run_id = _new_run(pg)
    out = pg.value(
        f"""BEGIN;
        UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';
        SELECT txid_current() = (SELECT xmin::text::bigint FROM public.domain_event_outbox
                                  WHERE aggregate_id = '{run_id}');
        COMMIT;"""
    )
    assert out == "t"  # same transaction id wrote the run change and the event


def test_non_terminal_and_repeat_updates_emit_nothing(pg):
    run_id = _new_run(pg)
    pg.psql(f"UPDATE public.workflow_runs SET status = 'pending_approval' WHERE id = '{run_id}';")
    pg.psql(f"UPDATE public.workflow_runs SET status = 'running' WHERE id = '{run_id}';")
    assert _events(pg) == []
    pg.psql(f"UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';")
    pg.psql(f"UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';")
    pg.psql(f"UPDATE public.workflow_runs SET parameters = '{{\"outcome_finalized\": true}}' WHERE id = '{run_id}';")
    assert len(_events(pg)) == 1


def test_terminal_reclassification_emits_a_second_event(pg):
    run_id = _new_run(pg)
    pg.psql(f"UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';")
    pg.psql(f"UPDATE public.workflow_runs SET status = 'verification_inconclusive' WHERE id = '{run_id}';")
    keys = [e["idempotency_key"] for e in _events(pg)]
    assert keys == [f"{run_id}:completed", f"{run_id}:verification_inconclusive"]


def test_insert_as_terminal_emits(pg):
    _new_run(pg, status="failed")
    assert len(_events(pg, "execution.outcome_finalized")) == 1


def test_same_transition_replayed_is_deduplicated(pg):
    run_id = _new_run(pg)
    pg.psql(f"UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';")
    pg.psql(f"UPDATE public.workflow_runs SET status = 'running' WHERE id = '{run_id}';")
    pg.psql(f"UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';")
    assert len(_events(pg)) == 1  # (event_type, idempotency_key) unique, ON CONFLICT DO NOTHING


def test_connector_disconnect_emits_once(pg):
    cid = pg.value(f"INSERT INTO public.connectors (org_id, type) VALUES ('{ORG}', 'hubspot') RETURNING id;")
    pg.psql(f"UPDATE public.connectors SET status = 'error' WHERE id = '{cid}';")
    assert _events(pg) == []
    pg.psql(f"UPDATE public.connectors SET deleted_at = now(), status = 'disconnected' WHERE id = '{cid}';")
    pg.psql(f"UPDATE public.connectors SET deleted_at = now() WHERE id = '{cid}';")  # already gone
    events = _events(pg, "source.disconnected")
    assert len(events) == 1
    assert events[0]["payload"]["connector_type"] == "hubspot"
    assert events[0]["payload"]["hard_deleted"] is False
    # Hard delete of an already-disconnected row does not emit again.
    pg.psql(f"DELETE FROM public.connectors WHERE id = '{cid}';")
    assert len(_events(pg, "source.disconnected")) == 1


def test_connected_source_hard_deleted_by_org_cascade_emits(pg):
    org2 = "33333333-3333-4333-8333-333333333333"
    pg.psql(f"INSERT INTO public.organizations VALUES ('{org2}');")
    pg.psql(f"INSERT INTO public.connectors (org_id, type) VALUES ('{org2}', 'zendesk');")
    pg.psql(f"DELETE FROM public.organizations WHERE id = '{org2}';")
    events = _events(pg, "source.disconnected")
    assert len(events) == 1 and events[0]["payload"]["hard_deleted"] is True
    assert events[0]["org_id"] == org2  # event outlives the org (no FK)


# ---------------------------------------------------------------- security


def test_user_jwt_write_still_emits_but_cannot_read_outbox(pg):
    run_id = _new_run(pg)
    pg.psql(
        f"""SET ROLE authenticated;
        SELECT set_config('request.jwt.claim.sub', '{USER}', false);
        UPDATE public.workflow_runs SET status = 'cancelled' WHERE id = '{run_id}';
        RESET ROLE;"""
    )
    assert len(_events(pg)) == 1  # SECURITY DEFINER trigger wrote it
    denied = pg.psql("SET ROLE authenticated; SELECT count(*) FROM public.domain_event_outbox;", check=False)
    assert denied.returncode != 0 and "permission denied" in denied.stderr
    denied = pg.psql("SET ROLE anon; SELECT * FROM public.claim_domain_events('x', 1, 30);", check=False)
    assert denied.returncode != 0 and "permission denied" in denied.stderr
    allowed = pg.psql("SET ROLE service_role; SELECT count(*) FROM public.claim_domain_events('svc', 1, 30);")
    assert allowed.stdout.strip() == "1"


def test_outbox_has_rls_enabled(pg):
    assert pg.value("SELECT relrowsecurity FROM pg_class WHERE relname = 'domain_event_outbox';") == "t"


# ---------------------------------------------------------------- relay RPCs


def _seed(pg, n: int) -> None:
    pg.psql(
        f"""INSERT INTO public.domain_event_outbox (org_id, event_type, aggregate_type, aggregate_id, idempotency_key)
        SELECT '{ORG}', 'test.event', 'test', g::text, 'k' || g FROM generate_series(1, {n}) g;"""
    )


def test_concurrent_claimers_never_share_an_event(pg):
    _seed(pg, 200)

    def claim(worker: str) -> list[str]:
        out = pg.value(
            f"SELECT string_agg(id::text, ',') FROM public.claim_domain_events('{worker}', 25, 60);"
        )
        return [x for x in out.split(",") if x]

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(claim, [f"w{i}" for i in range(8)]))
    claimed = [i for b in batches for i in b]
    assert len(claimed) == 200
    assert len(set(claimed)) == 200  # no event handed to two workers
    assert pg.value("SELECT count(DISTINCT lease_owner) FROM public.domain_event_outbox;") == "8"


def test_claim_skips_rows_locked_by_another_session(pg):
    _seed(pg, 3)
    # Session A holds a row lock on the first event for 2s while B claims.
    holder = subprocess.Popen(
        [str(PG_BIN / "psql"), "-h", str(pg.sock), "-p", pg.port, "-U", "postgres", "-d", "postgres",
         "-X", "-q", "-At", "-c",
         "BEGIN; SELECT id FROM public.domain_event_outbox ORDER BY id LIMIT 1 FOR UPDATE; SELECT pg_sleep(2); COMMIT;"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    import time

    time.sleep(0.7)
    got = pg.value("SELECT count(*) FROM public.claim_domain_events('b', 10, 60);")
    holder.wait(timeout=10)
    assert got == "2"  # did not block, did not take the locked row


def test_lease_expiry_lets_another_worker_reclaim_and_fences_the_old_one(pg):
    _seed(pg, 1)
    eid = pg.value("SELECT id FROM public.claim_domain_events('old', 1, 60);")
    assert pg.value("SELECT count(*) FROM public.claim_domain_events('new', 1, 60);") == "0"  # lease holds
    pg.psql("UPDATE public.domain_event_outbox SET lease_expires_at = now() - interval '1 second';")
    assert pg.value("SELECT id FROM public.claim_domain_events('new', 1, 60);") == eid
    assert pg.value(f"SELECT attempts FROM public.domain_event_outbox WHERE id = {eid};") == "2"
    assert pg.value(f"SELECT public.complete_domain_event({eid}, 'old', '{{}}');") == "f"  # fenced
    assert pg.value(f"SELECT public.fail_domain_event({eid}, 'old', 'x', '{{}}', 5);") == ""
    assert pg.value(f"SELECT public.complete_domain_event({eid}, 'new', ARRAY['h1']);") == "t"
    row = json.loads(pg.value(f"SELECT row_to_json(o) FROM public.domain_event_outbox o WHERE id = {eid};"))
    assert row["status"] == "delivered" and row["lease_owner"] is None and row["delivered_handlers"] == ["h1"]


def test_fail_schedules_retry_keeps_progress_then_dead_letters(pg):
    pg.psql(
        f"""INSERT INTO public.domain_event_outbox
        (org_id, event_type, aggregate_type, aggregate_id, idempotency_key, max_attempts)
        VALUES ('{ORG}', 'test.event', 'test', '1', 'k1', 2);"""
    )
    eid = pg.value("SELECT id FROM public.claim_domain_events('w', 1, 60);")
    assert pg.value(f"SELECT public.fail_domain_event({eid}, 'w', 'boom', ARRAY['h1'], 3600);") == "pending"
    assert pg.value("SELECT count(*) FROM public.claim_domain_events('w', 1, 60);") == "0"  # backing off
    row = json.loads(pg.value(f"SELECT row_to_json(o) FROM public.domain_event_outbox o WHERE id = {eid};"))
    assert row["delivered_handlers"] == ["h1"] and row["last_error"] == "boom" and row["attempts"] == 1
    pg.psql(f"UPDATE public.domain_event_outbox SET available_at = now() WHERE id = {eid};")
    assert pg.value("SELECT id FROM public.claim_domain_events('w', 1, 60);") == eid
    assert pg.value(f"SELECT public.fail_domain_event({eid}, 'w', 'boom again', ARRAY['h1'], 1);") == "dead"
    assert pg.value("SELECT count(*) FROM public.claim_domain_events('w', 5, 60);") == "0"


def test_crashed_worker_on_final_attempt_is_dead_lettered(pg):
    pg.psql(
        f"""INSERT INTO public.domain_event_outbox
        (org_id, event_type, aggregate_type, aggregate_id, idempotency_key, max_attempts)
        VALUES ('{ORG}', 'test.event', 'test', '1', 'k1', 1);"""
    )
    pg.value("SELECT id FROM public.claim_domain_events('crashed', 1, 60);")
    pg.psql("UPDATE public.domain_event_outbox SET lease_expires_at = now() - interval '1 second';")
    assert pg.value("SELECT count(*) FROM public.claim_domain_events('w', 1, 60);") == "0"
    assert pg.value("SELECT status FROM public.domain_event_outbox;") == "dead"


def test_stats_and_prune(pg):
    _seed(pg, 4)
    ids = pg.value("SELECT string_agg(id::text, ',') FROM public.claim_domain_events('w', 2, 60);").split(",")
    pg.psql(f"SELECT public.complete_domain_event({ids[0]}, 'w', '{{}}');")
    stats = json.loads(pg.value("SELECT public.domain_event_outbox_stats();"))
    assert stats["pending"] == 2 and stats["processing"] == 1 and stats["delivered"] == 1
    assert stats["dead"] == 0 and stats["oldest_pending_age_seconds"] >= 0
    assert pg.value("SELECT public.prune_domain_events(14, 100);") == "0"  # too recent
    pg.psql(f"UPDATE public.domain_event_outbox SET delivered_at = now() - interval '15 days' WHERE id = {ids[0]};")
    assert pg.value("SELECT public.prune_domain_events(14, 100);") == "1"
    assert pg.value("SELECT count(*) FROM public.domain_event_outbox;") == "3"


def test_lease_state_constraint_rejects_inconsistent_rows(pg):
    bad = pg.psql(
        f"""INSERT INTO public.domain_event_outbox
        (org_id, event_type, aggregate_type, aggregate_id, idempotency_key, status)
        VALUES ('{ORG}', 'test.event', 'test', '1', 'k1', 'processing');""",
        check=False,
    )
    assert bad.returncode != 0 and "domain_event_outbox_lease_consistent" in bad.stderr
    bad = pg.psql(
        f"""INSERT INTO public.domain_event_outbox
        (org_id, event_type, aggregate_type, aggregate_id, idempotency_key)
        VALUES ('{ORG}', 'NotDotted', 'test', '1', 'k1');""",
        check=False,
    )
    assert bad.returncode != 0


# ---------------------------------------------------------------- relay end to end


class _PsqlRpcClient:
    """Minimal supabase-py stand-in: ``rpc(name, params).execute()`` over psql."""

    def __init__(self, pg: _Pg) -> None:
        self._pg = pg

    @staticmethod
    def _lit(value) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, list):
            inner = ",".join(_PsqlRpcClient._lit(str(v)) for v in value)
            return f"ARRAY[{inner}]::text[]"
        return "'" + str(value).replace("'", "''") + "'"

    def rpc(self, name: str, params: dict):
        args = ", ".join(f"{k} => {self._lit(v)}" for k, v in params.items())
        pg = self._pg

        class _Call:
            def execute(self_inner):
                if name == "claim_domain_events":
                    out = pg.value(f"SELECT coalesce(json_agg(c), '[]') FROM public.{name}({args}) c;")
                else:
                    out = pg.value(f"SELECT to_json(public.{name}({args}));")
                from types import SimpleNamespace

                return SimpleNamespace(data=json.loads(out) if out else None)

        return _Call()


def test_relays_on_two_replicas_deliver_each_event_exactly_once(pg):
    from app.services import domain_events as de

    for _ in range(60):
        run_id = _new_run(pg)
        pg.psql(f"UPDATE public.workflow_runs SET status = 'completed' WHERE id = '{run_id}';")
    handled: list[str] = []
    de.reset_domain_event_handlers_for_tests()
    de.register_domain_event_handler(
        de.EVENT_EXECUTION_OUTCOME_FINALIZED, "record", lambda c, e: handled.append(e["event_id"])
    )
    try:
        relays = [
            de.DomainEventRelay(_PsqlRpcClient(pg), worker_id=f"replica-{i}", batch_size=7)
            for i in range(2)
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            for _ in range(6):
                list(pool.map(lambda r: r.run_once(), relays))
    finally:
        de.reset_domain_event_handlers_for_tests()
    assert len(handled) == 60 and len(set(handled)) == 60
    stats = json.loads(pg.value("SELECT public.domain_event_outbox_stats();"))
    assert stats["delivered"] == 60 and stats["pending"] == 0 and stats["processing"] == 0


def test_relay_failure_is_persisted_and_retried_on_real_db(pg):
    from app.services import domain_events as de

    run_id = _new_run(pg)
    pg.psql(f"UPDATE public.workflow_runs SET status = 'failed' WHERE id = '{run_id}';")
    attempts: list[int] = []

    def flaky(client, event):
        attempts.append(event["attempts"])
        if event["attempts"] == 1:
            raise RuntimeError("transient")

    de.reset_domain_event_handlers_for_tests()
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "ok", lambda c, e: None)
    de.register_domain_event_handler(de.EVENT_EXECUTION_OUTCOME_FINALIZED, "flaky", flaky)
    try:
        relay = de.DomainEventRelay(_PsqlRpcClient(pg), worker_id="w")
        first = relay.run_once()
        row = json.loads(pg.value("SELECT row_to_json(o) FROM public.domain_event_outbox o;"))
        assert first.retried == 1 and row["status"] == "pending" and row["delivered_handlers"] == ["ok"]
        assert "transient" in row["last_error"]
        pg.psql("UPDATE public.domain_event_outbox SET available_at = now();")  # skip the backoff wait
        second = relay.run_once()
    finally:
        de.reset_domain_event_handlers_for_tests()
    assert second.delivered == 1 and attempts == [1, 2]
    row = json.loads(pg.value("SELECT row_to_json(o) FROM public.domain_event_outbox o;"))
    assert row["status"] == "delivered" and row["delivered_handlers"] == ["ok", "flaky"]
