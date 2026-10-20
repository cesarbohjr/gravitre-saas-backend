"""Public promotion code catalog: idempotent migration, service-role-only access,
schema invariants, and exactly-once redemption under concurrency."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg
ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
MIGRATION = (MIGRATIONS / "20261019180000_public_promotion_codes.sql").read_text()
BOOTSTRAP = f"""
CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.organizations(id uuid primary key);
INSERT INTO public.organizations VALUES('{ORG}');
"""
INSERT_CODE = (
    "INSERT INTO public.promotion_codes(stripe_promotion_code_id,stripe_coupon_id,code,percent_off,duration,duration_in_months)"
    " VALUES('promo_1','coupon_1','LAUNCH30',30,'repeating',3);"
)


@pytest.fixture
def pg():
    # Applying twice proves the migration is idempotent.
    with pg_cluster(BOOTSTRAP, MIGRATION, MIGRATION) as db:
        yield db


def test_browser_roles_cannot_read_or_write(pg):
    pg.psql(INSERT_CODE)
    for role in ("anon", "authenticated"):
        denied = pg.psql(f"SET ROLE {role}; SELECT count(*) FROM public.promotion_codes;", check=False)
        assert denied.returncode != 0
        denied = pg.psql(
            f"SET ROLE {role}; SELECT public.record_promotion_code_redemption('k','promo_1',null,'x','{{}}');",
            check=False,
        )
        assert denied.returncode != 0


@pytest.mark.parametrize(
    "values",
    [
        "('p2','c2','lowercase',30,null,null,'forever',null)",  # code must be upper-case
        "('p3','c3','BOTH',30,500,'usd','forever',null)",  # percent xor amount
        "('p4','c4','NOMONTHS',30,null,null,'repeating',null)",  # repeating needs months
        "('p5','c5','ONCEMONTHS',30,null,null,'once',2)",  # months only for repeating
    ],
)
def test_schema_rejects_inconsistent_discounts(pg, values):
    result = pg.psql(
        "INSERT INTO public.promotion_codes(stripe_promotion_code_id,stripe_coupon_id,code,percent_off,"
        f"amount_off_cents,currency,duration,duration_in_months) VALUES {values};",
        check=False,
    )
    assert result.returncode != 0


def test_only_one_active_code_per_name(pg):
    pg.psql(INSERT_CODE)
    dup = INSERT_CODE.replace("promo_1", "promo_2").replace("coupon_1", "coupon_2")
    assert pg.psql(dup, check=False).returncode != 0
    pg.psql("UPDATE public.promotion_codes SET active=false;")
    assert pg.psql(dup, check=False).returncode == 0


def test_concurrent_redemption_signals_count_once(pg):
    pg.psql(INSERT_CODE)
    call = (
        "SET ROLE service_role; SELECT public.record_promotion_code_redemption("
        f"'redeemed:promo_1:sub_1','promo_1','{ORG}','checkout.session.completed','{{}}');"
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: pg.value(call), range(4)))
    assert sorted(results) == ["f", "f", "f", "t"]
    assert pg.value("SELECT times_redeemed FROM public.promotion_codes;") == "1"
    assert pg.value("SELECT count(*) FROM public.promotion_code_events WHERE event_type='redeemed';") == "1"


def test_unknown_stripe_code_is_recorded_without_bumping(pg):
    pg.psql(INSERT_CODE)
    assert pg.value(
        "SET ROLE service_role; SELECT public.record_promotion_code_redemption("
        "'redeemed:promo_dash:sub_2','promo_dash',null,'invoice.paid','{}');"
    ) == "t"
    assert pg.value("SELECT times_redeemed FROM public.promotion_codes;") == "0"
