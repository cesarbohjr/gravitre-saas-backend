"""Write invoke idempotency ledger — real PostgreSQL acceptance (disposable cluster)."""
from __future__ import annotations

import concurrent.futures
import json

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261014100000_write_invoke_idempotency.sql"

ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

pytestmark = requires_pg

BOOTSTRAP_SQL = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid $$;
GRANT USAGE ON SCHEMA public, auth TO anon, authenticated, service_role;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
INSERT INTO public.organizations VALUES ('{ORG_A}'), ('{ORG_B}');
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated;
"""


def _claim(pg, org: str, key: str, *, role: str = "service_role") -> dict:
    sql = f"""
SET ROLE {role};
SELECT public.claim_write_invoke_idempotency(
  '{org}'::uuid,
  '{key}',
  'hubspot.contacts.update',
  'logical-1',
  60
)::text;
"""
    raw = pg.psql(sql).stdout.strip()
    return json.loads(raw)


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("TRUNCATE public.write_invoke_idempotency;")
    yield


def test_concurrent_claims_single_winner(pg):
    key = "invoke:concurrent-1"

    def once():
        return _claim(pg, ORG_A, key)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: once(), range(8)))
    claimed = sum(1 for r in results if r.get("outcome") == "claimed")
    blocked = sum(1 for r in results if r.get("outcome") == "blocked")
    assert claimed == 1
    assert blocked == 7


def test_org_boundary_same_key(pg):
    a = _claim(pg, ORG_A, "shared-key")
    b = _claim(pg, ORG_B, "shared-key")
    assert a["outcome"] == "claimed"
    assert b["outcome"] == "claimed"


def test_completed_replay(pg):
    key = "invoke:replay-1"
    assert _claim(pg, ORG_A, key)["outcome"] == "claimed"
    pg.psql(
        f"""
SET ROLE service_role;
UPDATE public.write_invoke_idempotency
SET status = 'completed',
    result = '{{"success": true, "action": "hubspot.contacts.update", "data": {{"id": "1"}}}}'::jsonb,
    lease_expires_at = NULL
WHERE org_id = '{ORG_A}' AND idempotency_key = '{key}';
"""
    )
    replay = _claim(pg, ORG_A, key)
    assert replay["outcome"] == "replay"
    assert replay["result"]["success"] is True


def test_uncertain_blocks_retry(pg):
    key = "invoke:uncertain-1"
    assert _claim(pg, ORG_A, key)["outcome"] == "claimed"
    pg.psql(
        f"""
SET ROLE service_role;
UPDATE public.write_invoke_idempotency SET status = 'uncertain', lease_expires_at = NULL
WHERE org_id = '{ORG_A}' AND idempotency_key = '{key}';
"""
    )
    blocked = _claim(pg, ORG_A, key)
    assert blocked["outcome"] == "blocked"
    assert blocked["status"] == "uncertain"


def test_expired_lease_reclaimed(pg):
    key = "invoke:lease-1"
    assert _claim(pg, ORG_A, key)["outcome"] == "claimed"
    pg.psql(
        f"""
SET ROLE service_role;
UPDATE public.write_invoke_idempotency
SET lease_expires_at = now() - interval '1 minute'
WHERE org_id = '{ORG_A}' AND idempotency_key = '{key}';
"""
    )
    again = _claim(pg, ORG_A, key)
    assert again["outcome"] == "claimed"


def test_authenticated_cannot_insert(pg):
    err = pg.psql(
        f"""
SET ROLE authenticated;
SET request.jwt.claim.sub = '11111111-1111-4111-8111-111111111111';
INSERT INTO public.write_invoke_idempotency (org_id, idempotency_key, invoke_action, status)
VALUES ('{ORG_A}', 'bad', 'x.y', 'completed');
""",
        check=False,
    )
    assert err.returncode != 0
    assert "permission denied" in (err.stderr + err.stdout).lower()


def test_authenticated_cannot_call_claim_rpc(pg):
    err = pg.psql(
        f"""
SET ROLE authenticated;
SELECT public.claim_write_invoke_idempotency('{ORG_A}'::uuid, 'k', 'a', 'l', 30);
""",
        check=False,
    )
    assert err.returncode != 0
