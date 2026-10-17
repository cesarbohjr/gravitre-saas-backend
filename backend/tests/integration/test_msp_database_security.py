"""Isolated PostgreSQL integration checks for MSP delegation security.

Run only against a disposable Supabase database with migrations applied:
  MSP_TEST_DATABASE_URL=postgresql://... pytest -q backend/tests/integration/test_msp_database_security.py

Never point this suite at production. No service-role HTTP credentials required.
"""
import os
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("MSP_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="MSP_TEST_DATABASE_URL required (isolated database only)")


@pytest.fixture
def conn():
    with psycopg.connect(DSN, autocommit=False) as db:
        with db.cursor() as cur:
            cur.execute("BEGIN")
        yield db
        db.rollback()


def test_delegation_tables_not_readable_by_authenticated_role(conn):
    with conn.cursor() as cur:
        for table in ("msp_delegations", "msp_delegation_audit"):
            cur.execute(
                "SELECT has_table_privilege('authenticated', %s, 'SELECT'), "
                "has_table_privilege('authenticated', %s, 'INSERT'), "
                "has_table_privilege('anon', %s, 'SELECT')",
                (f"public.{table}", f"public.{table}", f"public.{table}"),
            )
            assert cur.fetchone() == (False, False, False)


def test_atomic_revoke_rpc_not_callable_by_authenticated_role(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT has_function_privilege('authenticated', "
            "'public.msp_revoke_delegation_atomic(uuid,uuid,uuid)', 'EXECUTE'), "
            "has_function_privilege('anon', "
            "'public.msp_revoke_delegation_atomic(uuid,uuid,uuid)', 'EXECUTE')"
        )
        assert cur.fetchone() == (False, False)


def test_delegation_rls_forced_and_no_parent_inheritance(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity "
            "FROM pg_class WHERE oid IN "
            "('public.msp_delegations'::regclass, 'public.msp_delegation_audit'::regclass)"
        )
        assert len(rows := cur.fetchall()) == 2
        assert all(rls and forced for _, rls, forced in rows)
        cur.execute(
            "SELECT COUNT(*) FROM pg_policies WHERE schemaname='public' "
            "AND tablename IN ('msp_delegations', 'msp_delegation_audit')"
        )
        assert cur.fetchone()[0] == 0


def test_revoke_without_actor_rolls_back_and_preserves_grant(conn):
    # Only exercise the mutation on disposable databases with at least two orgs.
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.organizations ORDER BY id LIMIT 2")
        orgs = [r[0] for r in cur.fetchall()]
        if len(orgs) < 2:
            pytest.fail("isolated database must seed two fixture organizations")
        delegation_id = uuid.uuid4()
        actor = uuid.uuid4()
        cur.execute(
            "INSERT INTO public.msp_delegations "
            "(id, provider_org_id, customer_org_id, grantee_user_id, tier, "
            "approved_by_customer_user_id, expires_at) "
            "VALUES (%s,%s,%s,%s,1,%s,now() + interval '1 hour')",
            (delegation_id, orgs[0], orgs[1], uuid.uuid4(), actor),
        )
        cur.execute(
            "SELECT action, actor_user_id FROM public.msp_delegation_audit "
            "WHERE delegation_id=%s", (delegation_id,)
        )
        assert cur.fetchall() == [("grant.created", actor)]
        cur.execute("SAVEPOINT revoke_attempt")
        with pytest.raises(psycopg.Error):
            cur.execute(
                "UPDATE public.msp_delegations SET revoked_at=now() WHERE id=%s",
                (delegation_id,),
            )
        cur.execute("ROLLBACK TO SAVEPOINT revoke_attempt")
        cur.execute("SELECT revoked_at FROM public.msp_delegations WHERE id=%s", (delegation_id,))
        assert cur.fetchone()[0] is None
        cur.execute(
            "SELECT count(*) FROM public.msp_delegation_audit "
            "WHERE delegation_id=%s AND action='grant.revoked'", (delegation_id,)
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT public.msp_revoke_delegation_atomic(%s,%s,%s)",
            (delegation_id, orgs[1], actor),
        )
        assert cur.fetchone()[0] is True
        cur.execute(
            "SELECT action, actor_user_id FROM public.msp_delegation_audit "
            "WHERE delegation_id=%s ORDER BY recorded_at, action", (delegation_id,)
        )
        assert cur.fetchall() == [("grant.created", actor), ("grant.revoked", actor)]


def test_audit_failure_rolls_back_grant(conn):
    """A deliberately rejected audit row must abort its parent grant insert."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM public.organizations ORDER BY id LIMIT 2")
        orgs = [r[0] for r in cur.fetchall()]
        if len(orgs) < 2:
            pytest.fail("isolated database must seed two fixture organizations")
        grant_id = uuid.uuid4()
        # The trigger records grant.created; a temporary transaction-local
        # constraint trigger rejects that audit event, forcing atomic rollback.
        cur.execute("SAVEPOINT before_audit_failure")
        cur.execute("""
            CREATE FUNCTION pg_temp.reject_msp_grant_audit() RETURNS trigger
            LANGUAGE plpgsql AS $body$
            BEGIN
              IF NEW.action = 'grant.created' THEN
                RAISE EXCEPTION 'test-injected audit failure';
              END IF;
              RETURN NEW;
            END;
            $body$
        """)
        cur.execute("""
            CREATE TRIGGER test_reject_msp_grant_audit
            BEFORE INSERT ON public.msp_delegation_audit
            FOR EACH ROW EXECUTE FUNCTION pg_temp.reject_msp_grant_audit()
        """)
        cur.execute("SAVEPOINT grant_attempt")
        with pytest.raises(psycopg.Error):
            cur.execute(
                "INSERT INTO public.msp_delegations "
                "(id, provider_org_id, customer_org_id, grantee_user_id, tier, "
                "approved_by_customer_user_id, expires_at) "
                "VALUES (%s,%s,%s,%s,1,%s,now() + interval '1 hour')",
                (grant_id, orgs[0], orgs[1], uuid.uuid4(), uuid.uuid4()),
            )
        cur.execute("ROLLBACK TO SAVEPOINT grant_attempt")
        cur.execute("SELECT count(*) FROM public.msp_delegations WHERE id=%s", (grant_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("ROLLBACK TO SAVEPOINT before_audit_failure")
