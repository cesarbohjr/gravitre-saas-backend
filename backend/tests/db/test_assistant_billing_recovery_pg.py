"""Real database recovery, plan-contract, poison and permission acceptance."""
import concurrent.futures
import subprocess

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_assistant_usage_atomic_pg import BOOTSTRAP, CALL_1, CALL_2, ORG_A, ORG_B

pytestmark = requires_pg


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(
        BOOTSTRAP,
        f"CREATE TABLE public.organizations(id uuid PRIMARY KEY); "
        f"INSERT INTO public.organizations VALUES ('{ORG_A}'), ('{ORG_B}'); "
        "GRANT INSERT, UPDATE, DELETE ON public.model_calls TO authenticated;",
        (MIGRATIONS / "20261015032117_assistant_usage_atomic.sql").read_text(),
        (MIGRATIONS / "20261015222156_atomic_usage_all_sources.sql").read_text(),
        (MIGRATIONS / "20261015232327_assistant_billing_recovery_contract.sql").read_text(),
    ) as server:
        yield server


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("TRUNCATE public.usage_tracking, public.overage_usage, public.billing_period_allowances; "
            "UPDATE public.model_calls SET billing_credits=8, billing_included=10, "
            "billing_environment='production', billing_settled_at=NULL, billing_attempts=0, "
            "billing_retry_at=now()-interval '1 hour', billing_last_error=NULL, "
            "created_at=now()-interval '20 minutes';")
    yield


def _settle(pg, call=CALL_1, org=ORG_A):
    return pg.value("SET ROLE service_role; SELECT public.settle_assistant_model_usage("
                    f"'{org}', '{call}');")


def test_concurrent_recovery_replays_do_not_double_charge(pg):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: _settle(pg), range(2)))
    assert sorted(results) == ["duplicate", "inserted"]
    assert _settle(pg, CALL_2) == "inserted"
    assert pg.value("SELECT sum(quantity) FROM public.usage_tracking;") == "16"
    assert pg.value("SELECT sum(quantity) FROM public.overage_usage;") == "6"
    assert pg.value("SELECT count(*) FROM public.model_calls WHERE billing_settled_at IS NOT NULL;") == "2"


def test_changed_allowance_does_not_reinterpret_prior_usage(pg):
    assert _settle(pg) == "inserted"
    pg.psql(f"UPDATE public.model_calls SET billing_included=20 WHERE id='{CALL_2}';")
    with pytest.raises(subprocess.CalledProcessError) as error:
        _settle(pg, CALL_2)
    assert "Billing allowance changed" in error.value.stderr
    assert pg.value("SELECT count(*) FROM public.usage_tracking;") == "1"
    assert pg.value(f"SELECT billing_settled_at IS NULL FROM public.model_calls WHERE id='{CALL_2}';") == "t"


def test_batch_excludes_legacy_and_bounds_work(pg):
    pg.psql(f"UPDATE public.model_calls SET billing_credits=NULL WHERE id='{CALL_2}';")
    # At the UTC month boundary the aged call belongs to the closed month and
    # must remain excluded, rather than making this test depend on wall clock.
    eligible = pg.value("SELECT count(*) FROM public.model_calls WHERE billing_credits IS NOT NULL "
                        "AND created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';")
    result = pg.value("SET ROLE service_role; SELECT public.recover_assistant_model_usage(1)->>'settled';")
    assert result == eligible
    assert pg.value(f"SELECT billing_settled_at IS NULL FROM public.model_calls WHERE id='{CALL_2}';") == "t"
    assert pg.psql("SET ROLE service_role; SELECT public.recover_assistant_model_usage(501);",
                   check=False).returncode != 0


def test_poison_backoff_does_not_block_other_calls(pg):
    pg.psql(f"UPDATE public.model_calls SET turn_id='not-assistant' WHERE id='{CALL_1}';")
    try:
        eligible = pg.value("SELECT count(*) FROM public.model_calls WHERE "
                            "created_at >= date_trunc('month', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC';")
        assert pg.value("SET ROLE service_role; SELECT public.recover_assistant_model_usage(100)->>'errors';") == (
            "1" if eligible == "2" else "0"
        )
        if eligible == "2":
            assert pg.value(f"SELECT billing_attempts FROM public.model_calls WHERE id='{CALL_1}';") == "1"
            assert pg.value(f"SELECT billing_last_error FROM public.model_calls WHERE id='{CALL_1}';") == "22023"
            assert pg.value("SET ROLE service_role; SELECT public.recover_assistant_model_usage(100)->>'scanned';") == "0"
    finally:
        pg.psql(f"UPDATE public.model_calls SET turn_id='assistant:turn-1' WHERE id='{CALL_1}';")


def test_wrong_tenant_and_client_mutations_are_denied(pg):
    assert pg.psql("SET ROLE service_role; SELECT public.settle_assistant_model_usage("
                   f"'{ORG_B}', '{CALL_1}');", check=False).returncode != 0
    assert pg.psql("SET ROLE authenticated; SELECT public.recover_assistant_model_usage(1);",
                   check=False).returncode != 0
    assert pg.psql("SET ROLE authenticated; UPDATE public.model_calls SET billing_credits=999;",
                   check=False).returncode != 0
    assert pg.psql("SET ROLE authenticated; SELECT * FROM public.billing_period_allowances;",
                   check=False).returncode != 0


def test_failed_overage_rolls_back_settlement_marker(pg):
    assert _settle(pg) == "inserted"
    pg.psql("""
CREATE FUNCTION public.reject_recovery_overage() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'test overage failure'; END $$;
CREATE TRIGGER reject_recovery_overage BEFORE INSERT ON public.overage_usage
FOR EACH ROW EXECUTE FUNCTION public.reject_recovery_overage();
""")
    try:
        with pytest.raises(subprocess.CalledProcessError):
            _settle(pg, CALL_2)
        assert pg.value("SELECT count(*) FROM public.usage_tracking;") == "1"
        assert pg.value(f"SELECT billing_settled_at IS NULL FROM public.model_calls WHERE id='{CALL_2}';") == "t"
    finally:
        pg.psql("DROP TRIGGER reject_recovery_overage ON public.overage_usage; "
                "DROP FUNCTION public.reject_recovery_overage();")
