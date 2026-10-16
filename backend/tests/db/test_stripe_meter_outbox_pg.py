"""Real PostgreSQL fencing, ledger identity and cross-org denial tests."""
from __future__ import annotations

import concurrent.futures
import os

import pytest

from tests.db.pg_harness import MIGRATIONS, PG_BIN, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261016190000_stripe_meter_outbox.sql"
A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
U1 = "11111111-1111-4111-8111-111111111111"
U2 = "22222222-2222-4222-8222-222222222222"
U3 = "33333333-3333-4333-8333-333333333333"

if os.environ.get("GRAVITRE_REQUIRE_PG") == "1" and PG_BIN is None:
    pytest.fail("GRAVITRE_REQUIRE_PG=1 but PostgreSQL binaries not installed")

pytestmark = requires_pg

BOOTSTRAP = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
INSERT INTO public.organizations VALUES ('{A}'), ('{B}');
CREATE TABLE public.usage_tracking (
  id uuid PRIMARY KEY,org_id uuid NOT NULL,environment text,metric_type text,
  quantity integer,period_start date,period_end date,stripe_reported_at timestamptz
);
CREATE TABLE public.usage_records (
  id uuid PRIMARY KEY,org_id uuid NOT NULL,metric_type text,
  quantity integer,recorded_at timestamptz,stripe_reported_at timestamptz
);
GRANT SELECT ON public.organizations TO service_role;
GRANT SELECT, UPDATE ON public.usage_tracking, public.usage_records TO service_role;
INSERT INTO public.usage_tracking VALUES
 ('{U1}','{A}','production','ai_credits',8,'2026-10-01','2026-10-31',NULL),
 ('{U2}','{A}','production','ai_credits',7,'2026-10-01','2026-10-31',NULL);
INSERT INTO public.usage_records VALUES
 ('{U1}','{A}','research_lookups',8,'2026-10-01T10:00:00Z',NULL),
 ('{U2}','{A}','research_lookups',7,'2026-10-01T11:00:00Z',NULL),
 ('{U3}','{A}','research_lookups',2,'2026-10-31T23:59:59Z',NULL);
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP, MIGRATION.read_text()) as server:
        yield server


@pytest.fixture(autouse=True)
def clean(pg):
    pg.psql("TRUNCATE public.stripe_meter_outbox; UPDATE public.usage_tracking SET stripe_reported_at=NULL; UPDATE public.usage_records SET stripe_reported_at=NULL;")
    yield


def _stage(pg, metric, included=0, org=A):
    return pg.value(
        f"SET ROLE service_role; SELECT public.stage_stripe_meter_intents("
        f"'{org}','{metric}','2026-10-01','2026-10-31',{included}, 'cus_test', 'test_meter');"
    )


def test_exact_allowance_deltas_include_last_day(pg):
    assert _stage(pg, "research_lookups", 10) == "3"
    assert pg.value(
        "SELECT string_agg(quantity::text, ',' ORDER BY source_id) "
        "FROM public.stripe_meter_outbox WHERE metric_type='research_lookups';"
    ) == "0,5,2"
    assert pg.value(
        "SELECT count(*) FROM public.stripe_meter_outbox WHERE status='zero';"
    ) == "1"
    assert pg.value(
        "SELECT count(*) FROM public.usage_records WHERE stripe_reported_at IS NOT NULL;"
    ) == "1"


def test_staging_idempotent_and_allowance_change_fails_closed(pg):
    assert _stage(pg, "research_lookups", 10) == "3"
    assert _stage(pg, "research_lookups", 10) == "0"
    assert pg.psql(
        f"SET ROLE service_role; SELECT public.stage_stripe_meter_intents("
        f"'{A}','research_lookups','2026-10-01','2026-10-31',11, 'cus_test', 'test_meter');", check=False
    ).returncode != 0


def test_parallel_claims_disjoint_and_cannot_reclaim(pg):
    assert _stage(pg, "ai_credits") == "2"

    def claim():
        return pg.psql(
            f"SET ROLE service_role; SELECT id FROM public.claim_stripe_meter_intents("
            f"'{A}','ai_credits',1);"
        ).stdout

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(lambda _: claim(), range(2)))
    assert first != second
    assert pg.value(
        "SELECT count(*) FROM public.stripe_meter_outbox WHERE status='sending';"
    ) == "2"
    assert pg.value(
        f"SET ROLE service_role; SELECT count(*) FROM public.claim_stripe_meter_intents('{A}','ai_credits',100);"
    ) == "0"


def test_ack_fences_claim_and_marks_source_atomically(pg):
    assert _stage(pg, "ai_credits") == "2"
    pg.psql(
        f"SET ROLE service_role; SELECT id FROM public.claim_stripe_meter_intents('{A}','ai_credits',1);"
    )
    assert pg.value(
        "SET ROLE service_role; SELECT public.ack_stripe_meter_intent("
        "(SELECT id FROM public.stripe_meter_outbox WHERE status='sending' LIMIT 1),"
        "'99999999-9999-4999-8999-999999999999');"
    ) == "f"
    assert pg.value("SELECT count(*) FROM public.usage_tracking WHERE stripe_reported_at IS NOT NULL;") == "0"
    assert pg.value(
        "SET ROLE service_role; SELECT public.ack_stripe_meter_intent(id,claim_token) "
        "FROM public.stripe_meter_outbox WHERE status='sending';"
    ) == "t"
    assert pg.value("SELECT count(*) FROM public.usage_tracking WHERE stripe_reported_at IS NOT NULL;") == "1"


def test_public_execute_denied_and_org_scope_guard(pg):
    assert _stage(pg, "ai_credits") == "2"
    resp = pg.psql(
        f"SET ROLE authenticated; SELECT * FROM public.claim_stripe_meter_intents('{A}','ai_credits',1);",
        check=False,
    )
    assert resp.returncode != 0
    assert "permission denied" in (resp.stdout + resp.stderr).lower()
    assert pg.value(
        f"SET ROLE service_role; SELECT count(*) FROM public.claim_stripe_meter_intents('{B}','ai_credits',10);"
    ) == "0"
