"""Real database concurrency and RLS for founder checkout reservations."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg
ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
GRANT = "11111111-1111-4111-8111-111111111111"
USER = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def pg():
    with pg_cluster(f"""
        CREATE ROLE anon NOLOGIN;
        CREATE ROLE authenticated NOLOGIN;
        CREATE ROLE service_role NOLOGIN BYPASSRLS;
        CREATE TABLE public.organizations (id uuid PRIMARY KEY);
        INSERT INTO public.organizations VALUES ('{ORG}'), ('{OTHER}');
    """, (MIGRATIONS / "20261019050504_customer_segments_and_founder_offers.sql").read_text()) as db:
        db.psql(f"""
            INSERT INTO public.org_commercial_profiles(org_id,customer_category) VALUES ('{ORG}','external');
            INSERT INTO public.org_promotional_grants(id,org_id,offer_type,trial_days) VALUES ('{GRANT}','{ORG}','trial',30);
        """)
        yield db


def claim(pg, org=ORG, price="price_base"):
    return pg.psql(f"SET ROLE service_role; SELECT checkout_attempt_id FROM public.reserve_founder_checkout('{org}','{GRANT}','cus_test','{price}','{USER}');", check=False)


def test_parallel_claims_return_one_attempt(pg):
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: claim(pg), range(4)))
    assert all(row.returncode == 0 for row in outcomes)
    assert len({row.stdout.strip() for row in outcomes}) == 1
    assert outcomes[0].stdout.strip()
    assert claim(pg, price="other_price").returncode != 0
    assert claim(pg, org=OTHER).returncode != 0


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_browser_cannot_read_or_reserve(pg, role):
    assert pg.psql(f"SET ROLE {role}; SELECT * FROM public.org_promotional_grants;", check=False).returncode != 0
    assert pg.psql(f"SET ROLE {role}; SELECT * FROM public.reserve_founder_checkout('{ORG}','{GRANT}','cus','price','{USER}');", check=False).returncode != 0


def test_expired_revoked_and_repeated_trials_denied(pg):
    pg.psql(f"UPDATE public.org_promotional_grants SET valid_until=now()-interval '1 second' WHERE id='{GRANT}';")
    assert claim(pg).returncode != 0
    pg.psql(f"UPDATE public.org_promotional_grants SET valid_until=NULL,status='revoked' WHERE id='{GRANT}';")
    assert claim(pg).returncode != 0
    pg.psql(f"UPDATE public.org_promotional_grants SET status='redeemed' WHERE id='{GRANT}'; INSERT INTO public.org_promotional_grants(org_id,offer_type,trial_days) VALUES ('{ORG}','trial',30);")
    assert claim(pg).returncode != 0


def test_ambiguous_claim_is_not_reclaimed_after_stripe_key_window(pg):
    assert claim(pg).returncode == 0
    pg.psql(f"UPDATE public.org_promotional_grants SET checkout_reserved_at=now()-interval '25 hours' WHERE id='{GRANT}';")
    assert claim(pg).returncode != 0
