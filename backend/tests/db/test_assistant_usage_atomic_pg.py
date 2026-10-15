"""Assistant usage/overage contract in a disposable real PostgreSQL cluster."""
from __future__ import annotations

import concurrent.futures
import os

import pytest

from tests.db.pg_harness import MIGRATIONS, PG_BIN, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261015032117_assistant_usage_atomic.sql"
ORG_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ORG_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CALL_1 = "11111111-1111-4111-8111-111111111111"
CALL_2 = "22222222-2222-4222-8222-222222222222"

if os.environ.get("GRAVITRE_REQUIRE_PG") == "1" and PG_BIN is None:
    pytest.fail("GRAVITRE_REQUIRE_PG=1 but PostgreSQL server binaries are not installed")

pytestmark = requires_pg

BOOTSTRAP = f"""
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.model_calls (
  id uuid PRIMARY KEY, org_id uuid NOT NULL, turn_id text, created_at timestamptz,
  model_name text, input_tokens int, output_tokens int
);
CREATE TABLE public.usage_tracking (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL,
  environment text NOT NULL, metric_type text NOT NULL, quantity int NOT NULL,
  period_start date NOT NULL, period_end date NOT NULL, model_name text,
  input_tokens int, output_tokens int, credits int, source text, source_id text,
  idempotency_key text
);
CREATE UNIQUE INDEX uq_usage_tracking_org_idempotency
  ON public.usage_tracking(org_id, idempotency_key);
CREATE TABLE public.overage_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL,
  environment text NOT NULL, metric_type text NOT NULL, quantity int NOT NULL,
  period_start date NOT NULL, period_end date NOT NULL, idempotency_key text
);
CREATE UNIQUE INDEX uq_overage_usage_org_idempotency
  ON public.overage_usage(org_id, idempotency_key);
GRANT SELECT ON public.model_calls TO service_role;
GRANT SELECT, INSERT ON public.usage_tracking, public.overage_usage TO service_role;
INSERT INTO public.model_calls VALUES
  ('{CALL_1}', '{ORG_A}', 'assistant:turn-1', '2026-09-30T23:59:59Z', 'test-model', 100, 50),
  ('{CALL_2}', '{ORG_A}', 'assistant:turn-2', '2026-09-30T23:59:59Z', 'test-model', 100, 50);
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP, MIGRATION.read_text()) as server:
        yield server


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("TRUNCATE public.usage_tracking, public.overage_usage;")
    yield


def _record(pg, call_id: str, quantity: int = 8, org_id: str = ORG_A, included: int = 10):
    return pg.value(
        f"SET ROLE service_role; SELECT public.record_assistant_model_usage("
        f"'{org_id}', '{call_id}', {quantity}, {included}, 'production');"
    )


def test_concurrent_calls_share_allowance_and_replays_do_not_charge_again(pg):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda call: _record(pg, call), (CALL_1, CALL_2)))
    assert outcomes == ["inserted", "inserted"]
    assert _record(pg, CALL_1) == "duplicate"
    assert pg.value("SELECT sum(quantity) FROM public.usage_tracking;") == "16"
    assert pg.value("SELECT sum(quantity) FROM public.overage_usage;") == "6"


def test_rpc_rejects_wrong_org_and_non_service_actor(pg):
    assert pg.psql(
        f"SET ROLE service_role; SELECT public.record_assistant_model_usage("
        f"'{ORG_B}', '{CALL_1}', 8, 10, 'production');", check=False,
    ).returncode != 0
    result = pg.psql(
        f"SET ROLE authenticated; SELECT public.record_assistant_model_usage("
        f"'{ORG_A}', '{CALL_1}', 8, 10, 'production');", check=False,
    )
    assert result.returncode != 0
    assert "permission denied" in (result.stdout + result.stderr).lower()


def test_duplicate_with_changed_quantity_is_rejected(pg):
    assert _record(pg, CALL_1) == "inserted"
    assert pg.psql(
        f"SET ROLE service_role; SELECT public.record_assistant_model_usage("
        f"'{ORG_A}', '{CALL_1}', 9, 10, 'production');", check=False,
    ).returncode != 0
    assert pg.value("SELECT count(*) FROM public.usage_tracking;") == "1"


def test_duplicate_with_changed_model_identity_is_rejected(pg):
    assert _record(pg, CALL_1) == "inserted"
    pg.psql(f"UPDATE public.usage_tracking SET model_name = 'wrong' WHERE source_id = '{CALL_1}';")
    assert pg.psql(
        f"SET ROLE service_role; SELECT public.record_assistant_model_usage("
        f"'{ORG_A}', '{CALL_1}', 8, 10, 'production');", check=False,
    ).returncode != 0
    assert pg.value("SELECT count(*) FROM public.usage_tracking;") == "1"


def test_overage_failure_rolls_back_usage(pg):
    pg.psql("""
CREATE FUNCTION public.reject_overage() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'simulated overage failure'; END $$;
CREATE TRIGGER fail_overage BEFORE INSERT ON public.overage_usage
FOR EACH ROW EXECUTE FUNCTION public.reject_overage();
""")
    try:
        assert _record(pg, CALL_1) == "inserted"
        assert pg.psql(
            f"SET ROLE service_role; SELECT public.record_assistant_model_usage("
            f"'{ORG_A}', '{CALL_2}', 8, 10, 'production');", check=False,
        ).returncode != 0
        assert pg.value("SELECT count(*) FROM public.usage_tracking;") == "1"
    finally:
        pg.psql("DROP TRIGGER fail_overage ON public.overage_usage; DROP FUNCTION public.reject_overage();")


def test_utc_period_comes_from_persisted_model_call(pg):
    assert _record(pg, CALL_1) == "inserted"
    assert pg.value("SELECT period_start FROM public.usage_tracking;") == "2026-09-01"
