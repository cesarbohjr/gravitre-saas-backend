"""Atomic autonomous approval claims on disposable PostgreSQL, including revocation."""
from __future__ import annotations
import concurrent.futures
import json
import os
import pytest
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_write_invoke_idempotency_pg import BOOTSTRAP_SQL, ORG_A

pytestmark = requires_pg
RUN = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
MIGRATION = MIGRATIONS / "20261016032018_write_invoke_idempotency.sql"
GRANTS = MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql"
ATOMIC = MIGRATIONS / "20261102095000_autonomous_atomic_write_claim.sql"
BOOT = BOOTSTRAP_SQL + f"""
CREATE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$ SELECT 'service_role'::text $$;
CREATE TABLE public.workflow_runs (
    id uuid PRIMARY KEY, org_id uuid NOT NULL,
    approval_status text, required_approvals integer);
INSERT INTO public.workflow_runs VALUES ('{RUN}', '{ORG_A}', 'approved', 1);
"""

def _call(pg, key):
    return json.loads(pg.psql(f"""SET ROLE service_role;
SELECT public.claim_approved_autonomous_write(
'{ORG_A}'::uuid, '{RUN}'::uuid, '{key}', 'hubspot.contacts.update', 'logical-1', 60)::text;
""").stdout.strip())

def test_atomic_approval_revocation_and_replay(tmp_path):
    with pg_cluster(BOOT, MIGRATION.read_text(), GRANTS.read_text(), ATOMIC.read_text()) as pg:
        first = _call(pg, "atomic-first")
        assert first["outcome"] == "claimed" and first["claim_token"]
        assert _call(pg, "atomic-first")["outcome"] == "blocked"
        pg.psql(f"UPDATE public.workflow_runs SET approval_status='revoked' WHERE id='{RUN}';")
        denied = _call(pg, "atomic-second")
        assert denied["outcome"] == "blocked"
        assert denied["reason"] == "approval_revoked_or_missing"
        assert pg.value("SELECT count(*) FROM public.write_invoke_idempotency;") == "1"
        pg.stop()
        opts=f"-k {pg.sock} -p {pg.port} -c listen_addresses='' -c fsync=off"
        import subprocess
        subprocess.run(pg._cmd("pg_ctl", "-D", str(pg.data), "-o", opts, "-w",
                               "-l", str(pg.root / "restart.log"), "start"),
                       check=True, capture_output=True)
        assert _call(pg, "atomic-first")["outcome"] == "blocked"
        assert _call(pg, "atomic-second")["outcome"] == "blocked"

def test_atomic_claim_same_key_has_single_winner():
    with pg_cluster(BOOT, MIGRATION.read_text(), GRANTS.read_text(), ATOMIC.read_text()) as pg:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            rows=list(pool.map(lambda _: _call(pg, "race-1"),range(6)))
        assert sum(row["outcome"] == "claimed" for row in rows) == 1
        assert sum(row["outcome"] == "blocked" for row in rows) == 5

def test_concurrent_revocation_wins_before_claim():
    """An uncommitted revocation holds the run lock until commit."""
    import threading
    import time
    with pg_cluster(BOOT, MIGRATION.read_text(), GRANTS.read_text(), ATOMIC.read_text()) as pg:
        started = threading.Event()
        errors = []
        def revoke():
            try:
                # Signal before transaction start, then allow it to acquire
                # the row lock before the claimant attempts the RPC.
                started.set()
                pg.psql(f"""BEGIN;
UPDATE public.workflow_runs SET approval_status='revoked' WHERE id='{RUN}';
SELECT pg_sleep(1);
COMMIT;""")
            except Exception as exc:
                errors.append(str(exc))
        thread=threading.Thread(target=revoke)
        thread.start()
        assert started.wait(timeout=2)
        time.sleep(.25)
        result=_call(pg, "concurrent-revoked")
        thread.join(timeout=5)
        assert not thread.is_alive() and not errors
        assert result["outcome"] == "blocked", result
        assert pg.value("SELECT count(*) FROM public.write_invoke_idempotency") == "0"
