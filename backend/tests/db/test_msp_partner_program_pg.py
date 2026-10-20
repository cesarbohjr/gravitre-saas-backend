"""MSP partner program migration against real PostgreSQL: invariants and lockdown."""
import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

MSP = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
CLIENT = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
USER = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
BOOTSTRAP = f"""
CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; CREATE ROLE service_role NOLOGIN BYPASSRLS;
CREATE TABLE public.organizations(id uuid primary key, name text, parent_org_id uuid);
CREATE TABLE public.org_billing(org_id uuid primary key references public.organizations(id), plan_code text, billing_status text);
INSERT INTO public.organizations(id,name) VALUES('{MSP}','MSP'),('{CLIENT}','Client'),('{OTHER}','Other');
GRANT SELECT,INSERT,UPDATE ON public.organizations,public.org_billing TO service_role;
"""
SQL = (MIGRATIONS / "20261019120000_msp_partner_program.sql").read_text()


@pytest.fixture
def pg():
    # Applied twice: the migration must be idempotent.
    with pg_cluster(BOOTSTRAP, SQL, SQL) as db:
        db.psql(f"UPDATE public.organizations SET account_type='msp' WHERE id='{MSP}';")
        yield db


def _insert(client: str, msp: str = MSP, status: str = "pending_client_approval") -> str:
    extra = ", access_level, approved_at" if status == "active" else ""
    extra_vals = ", 'full', now()" if status == "active" else ""
    return (
        "SET ROLE service_role; INSERT INTO public.msp_clients"
        f"(msp_org_id, client_org_id, plan_code, status, created_by{extra}) "
        f"VALUES('{msp}','{client}','node','{status}','{USER}'{extra_vals});"
    )


def test_defaults_and_client_link(pg):
    assert pg.value(f"SELECT account_type FROM public.organizations WHERE id='{CLIENT}'") == "standard"
    pg.psql(_insert(CLIENT, status="active"))
    assert pg.value("SELECT count(*) FROM public.msp_clients") == "1"


def test_one_live_relationship_per_client_but_history_allowed(pg):
    pg.psql(_insert(CLIENT))
    assert pg.psql(_insert(CLIENT), check=False).returncode != 0
    pg.psql("UPDATE public.msp_clients SET status='detached', detached_at=now();")
    pg.psql(_insert(CLIENT))
    assert pg.value("SELECT count(*) FROM public.msp_clients") == "2"


def test_msp_cannot_be_a_client_or_its_own_client(pg):
    assert pg.psql(_insert(MSP), check=False).returncode != 0
    pg.psql(f"UPDATE public.organizations SET account_type='msp' WHERE id='{OTHER}';")
    assert pg.psql(_insert(OTHER), check=False).returncode != 0
    # Managing org must be an MSP.
    assert pg.psql(_insert(CLIENT, msp=OTHER.replace("c", "e")), check=False).returncode != 0


def test_active_requires_access_and_approval(pg):
    bad = (
        "SET ROLE service_role; INSERT INTO public.msp_clients(msp_org_id,client_org_id,plan_code,status,created_by) "
        f"VALUES('{MSP}','{CLIENT}','node','active','{USER}');"
    )
    assert pg.psql(bad, check=False).returncode != 0
    wrong_plan = _insert(CLIENT).replace("'node'", "'enterprise'")
    assert pg.psql(wrong_plan, check=False).returncode != 0


def test_billing_source_constraint(pg):
    pg.psql(f"INSERT INTO public.org_billing(org_id,plan_code,billing_status) VALUES('{CLIENT}','node','trialing');")
    assert pg.value(f"SELECT billing_source FROM public.org_billing WHERE org_id='{CLIENT}'") == "self"
    assert pg.psql(f"UPDATE public.org_billing SET billing_source='msp' WHERE org_id='{CLIENT}';", check=False).returncode != 0
    pg.psql(f"UPDATE public.org_billing SET billing_source='msp', billed_by_org_id='{MSP}' WHERE org_id='{CLIENT}';")


@pytest.mark.parametrize("role", ["anon", "authenticated"])
def test_browser_roles_cannot_read_partner_tables(pg, role):
    for table in ("msp_clients", "msp_billing_accounts"):
        assert pg.psql(f"SET ROLE {role}; SELECT * FROM public.{table};", check=False).returncode != 0
    forced = pg.value(
        "SELECT bool_and(relforcerowsecurity) FROM pg_class "
        "WHERE relname IN ('msp_clients','msp_billing_accounts')"
    )
    assert forced == "t"
