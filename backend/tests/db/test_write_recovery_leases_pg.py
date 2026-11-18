"""Real PostgreSQL recovery-lease acceptance against disposable test cluster.

Checks claim expiration, service-role recovery leases, fencing, deferral,
and terminal replay without invoking any external provider.
"""
from __future__ import annotations

import json
import os
import pytest

from tests.db.pg_harness import MIGRATIONS, PG_BIN, pg_cluster, requires_pg

pytestmark = requires_pg
if os.environ.get("GRAVITRE_REQUIRE_PG") == "1" and PG_BIN is None:
    pytest.fail("GRAVITRE_REQUIRE_PG=1 but PostgreSQL server binaries are not installed")

ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BASE = MIGRATIONS / "20261016032018_write_invoke_idempotency.sql"
GRANTS = MIGRATIONS / "20261016032029_write_invoke_idempotency_grants.sql"
CONTEXT = MIGRATIONS / "20261118030000_write_recovery_context.sql"
DUE = MIGRATIONS / "20261118040000_write_recovery_due_queue.sql"
LEASES = MIGRATIONS / "20261118050000_write_recovery_leases.sql"

BOOTSTRAP = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE SCHEMA auth;
CREATE FUNCTION auth.role() RETURNS text LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.role',true),'') $$;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
GRANT USAGE ON SCHEMA public,auth TO anon,authenticated,service_role;
CREATE TABLE public.organizations(id uuid PRIMARY KEY);
INSERT INTO public.organizations VALUES ('{ORG}');
"""


@pytest.fixture(scope="module")
def pg():
    scripts = [BASE, GRANTS, CONTEXT, DUE, LEASES]
    with pg_cluster(BOOTSTRAP, *(p.read_text() for p in scripts)) as server:
        yield server


@pytest.fixture(autouse=True)
def clean(pg):
    pg.psql("TRUNCATE public.write_invoke_idempotency;")
    yield


def _json(pg, expression: str):
    sql = f"SET ROLE service_role; SET request.jwt.claim.role='service_role'; SELECT {expression}::text;"
    return json.loads(pg.psql(sql).stdout.strip())


def test_expired_write_is_leased_once_and_fenced_on_settlement(pg):
    key = "recovery-expiration"
    claimed = _json(pg, f"public.claim_write_invoke_idempotency('{ORG}'::uuid,'{key}','hubspot.contacts.update','logical',60)")
    token = claimed["claim_token"]
    bound = _json(pg, f"""public.bind_write_recovery_context(
       '{ORG}'::uuid,'{key}','{token}'::uuid,'hubspot.contacts.update',
       'conn-a','{{"email":"qa@example.invalid"}}'::jsonb)""")
    assert bound["outcome"] == "bound"
    pg.psql(f"""UPDATE public.write_invoke_idempotency
      SET lease_expires_at=now()-interval '1 minute'
      WHERE org_id='{ORG}' AND idempotency_key='{key}';""")
    leased = _json(pg, "coalesce((SELECT row_to_json(x) FROM public.claim_due_write_recoveries(1,120) AS x),'{}'::json)")
    assert leased["idempotency_key"] == key
    assert leased["connector_id"] == "conn-a"
    assert leased["original_args"] == {"email": "qa@example.invalid"}
    second = _json(pg, "coalesce((SELECT row_to_json(x) FROM public.claim_due_write_recoveries(1,120) AS x),'{}'::json)")
    assert second == {}
    stale = _json(pg, f"""public.settle_leased_write_recovery('{ORG}'::uuid,'{key}',gen_random_uuid(),
      'completed','{{"success":true}}'::jsonb)""")
    assert stale["outcome"] == "rejected"
    settled = _json(pg, f"""public.settle_leased_write_recovery(
      '{ORG}'::uuid,'{key}','{leased["recovery_lease_token"]}'::uuid,
      'completed','{{"success":true,"action":"hubspot.contacts.update","data":{{"id":"qa"}}}}'::jsonb)""")
    assert settled["outcome"] == "reconciled"
    replay = _json(pg, f"public.claim_write_invoke_idempotency('{ORG}'::uuid,'{key}','hubspot.contacts.update','logical',60)")
    assert replay["outcome"] == "replay"
    assert replay["result"]["data"]["id"] == "qa"


def test_unknown_recovery_deferred_not_immediately_released(pg):
    key = "recovery-defer"
    pg.psql(f"""INSERT INTO public.write_invoke_idempotency
      (org_id,idempotency_key,invoke_action,status,connector_id,original_args)
      VALUES('{ORG}','{key}','hubspot.contacts.create','uncertain',
        'conn-a','{{"email":"qa@example.invalid"}}'::jsonb);""")
    leased = _json(pg, "coalesce((SELECT row_to_json(x) FROM public.claim_due_write_recoveries(1,60) AS x),'{}'::json)")
    assert leased["idempotency_key"] == key
    defer = _json(pg, f"""public.defer_leased_write_recovery(
      '{ORG}'::uuid,'{key}','{leased["recovery_lease_token"]}'::uuid)""")
    assert defer["outcome"] == "deferred"
    next_one = _json(pg, "coalesce((SELECT row_to_json(x) FROM public.claim_due_write_recoveries(1,60) AS x),'{}'::json)")
    assert next_one == {}
    assert pg.value(f"SELECT status FROM public.write_invoke_idempotency WHERE idempotency_key='{key}';") == "uncertain"
