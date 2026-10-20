"""Atomic quota / topup money safety against real PostgreSQL, including races."""

from concurrent.futures import ThreadPoolExecutor
import pytest
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg
ORG = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
GRANT = "11111111-1111-4111-8111-111111111111"
BOOTSTRAP = f"""
CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.organizations(id uuid primary key);
CREATE TABLE public.org_billing(org_id uuid primary key,billing_status text,current_period_end timestamptz,stripe_customer_id text,stripe_subscription_id text);
CREATE TABLE public.subscriptions(org_id uuid primary key,status text,voice_enabled boolean default true,voice_auto_topup_enabled boolean default true,voice_auto_topup_minutes integer default 60,voice_auto_topup_threshold_minutes integer default 15,voice_auto_topup_max_charge_cents integer default 3600,voice_minutes_prepaid integer default 0);
CREATE TABLE public.usage_records(org_id uuid,metric_type text,quantity integer,recorded_at timestamptz default now());
CREATE TABLE public.billing_topup_events(id uuid primary key default gen_random_uuid(),org_id uuid,metric_type text,minutes integer,amount_cents integer,currency text default 'usd',source text,status text,stripe_payment_intent_id text,stripe_checkout_session_id text,created_at timestamptz default now(),completed_at timestamptz);
INSERT INTO public.organizations VALUES('{ORG}');
INSERT INTO public.org_billing VALUES('{ORG}','trialing',now()+interval '30 days','cus_test','sub_test');
INSERT INTO public.subscriptions(org_id,status) VALUES('{ORG}','active');
GRANT SELECT,INSERT,UPDATE ON public.organizations,public.org_billing,public.subscriptions,public.usage_records,public.billing_topup_events TO service_role;
"""


@pytest.fixture
def pg():
    with pg_cluster(
        BOOTSTRAP,
        (
            MIGRATIONS / "20261019050504_customer_segments_and_founder_offers.sql"
        ).read_text(),
        (MIGRATIONS / "20261019050855_founder_billing_safety.sql").read_text(),
    ) as db:
        db.psql(
            f"INSERT INTO public.org_commercial_profiles(org_id,customer_category) VALUES('{ORG}','external'); INSERT INTO public.org_promotional_grants(id,org_id,offer_type,trial_days,status) VALUES('{GRANT}','{ORG}','trial',30,'redeemed');"
        )
        yield db


def test_parallel_trial_admissions_cannot_exceed_quota(pg):
    def reserve(_):
        return pg.psql(
            f"SET ROLE service_role; SELECT public.reserve_founder_trial_units('{ORG}','research_lookups',1,2);",
            check=False,
        ).returncode

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(reserve, range(4)))
    assert outcomes.count(0) == 2
    assert (
        pg.value(
            f"SELECT trial_units_reserved->>'research_lookups' FROM public.org_promotional_grants WHERE id='{GRANT}';"
        )
        == "2"
    )


def test_topup_trial_denial_concurrent_claims_and_exactly_once_credit(pg):
    query = f"SET ROLE service_role; SELECT public.claim_voice_auto_topup('{ORG}',60,720,10);"
    assert pg.value(query) == ""
    pg.psql(
        f"UPDATE public.org_billing SET billing_status='active'; INSERT INTO public.usage_records(org_id,metric_type,quantity) VALUES('{ORG}','voice_minutes',10);"
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(lambda _: pg.value(query), range(4)))
    assert sum(bool(row) for row in rows) == 1
    event = pg.value("SELECT id FROM public.billing_topup_events;")
    complete = f"SET ROLE service_role; SELECT public.complete_voice_topup('{event}','{ORG}','cus_test',720,'usd','pi_test','');"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: pg.value(complete), range(4)))
    assert (
        pg.value(
            f"SELECT voice_minutes_prepaid FROM public.subscriptions WHERE org_id='{ORG}';"
        )
        == "60"
    )
    assert pg.value(query) == ""
    assert pg.psql(complete.replace("720", "721"), check=False).returncode != 0


def test_monthly_cap_and_pending_barrier(pg):
    pg.psql(
        f"UPDATE public.org_billing SET billing_status='active'; UPDATE public.subscriptions SET voice_auto_topup_monthly_cap_cents=719; INSERT INTO public.usage_records(org_id,metric_type,quantity) VALUES('{ORG}','voice_minutes',1000);"
    )
    assert (
        pg.value(
            f"SET ROLE service_role; SELECT public.claim_voice_auto_topup('{ORG}',60,720,10);"
        )
        == ""
    )


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_browser_cannot_call_billing_safety_functions(pg, role):
    assert (
        pg.psql(
            f"SET ROLE {role}; SELECT public.reserve_founder_trial_units('{ORG}','ai_credits',1,10);",
            check=False,
        ).returncode
        != 0
    )
    assert (
        pg.psql(
            f"SET ROLE {role}; SELECT * FROM public.billing_safety_alerts;", check=False
        ).returncode
        != 0
    )
