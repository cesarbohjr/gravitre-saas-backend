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


@pytest.mark.parametrize("provider_applied", [True, False])
def test_scheduled_recovery_settles_independent_receiver_without_redispatch(
    pg, tmp_path, provider_applied,
):
    """Cross service worker -> tenant ledger -> leased SQL -> independent receipt.

    The provider is a separate local HTTP process. Only its readback adapter is
    substituted; the actual Python recovery worker, SQL queue and settlement
    functions execute unchanged. No production provider is contacted.
    """
    import urllib.request
    from types import SimpleNamespace
    from unittest.mock import patch

    from app.services.tool_types import ToolContext
    from app.services.outcome_reconciliation import ReconciliationResult
    from app.services.write_recovery_worker import process_due_write_recoveries
    from tests.db.test_autonomous_independent_write_pg import IndependentFixture
    from tests.db.write_recovery_context_fixture import PgRecoveryClient

    key = "scheduled-recovery-" + ("applied" if provider_applied else "absent")
    args = {"email": "qa@example.invalid"}
    claim = _json(
        pg, f"public.claim_write_invoke_idempotency("
        f"'{ORG}'::uuid,'{key}','hubspot.contacts.create','test-approval',60)",
    )
    assert claim["outcome"] == "claimed"
    bound = _json(
        pg, f"public.bind_write_recovery_context("
        f"'{ORG}'::uuid,'{key}','{claim['claim_token']}'::uuid,"
        f"'hubspot.contacts.create','conn-a',"
        f"'{{\"email\":\"qa@example.invalid\"}}'::jsonb)",
    )
    assert bound["outcome"] == "bound"

    receiver = IndependentFixture(
        tmp_path / (key + ".sqlite3"), b"<h1>QA</h1>",
        capability="readback-qa",
    )
    try:
        if provider_applied:
            request = urllib.request.Request(
                receiver.origin + "/write",
                data=json.dumps({"cap": "readback-qa"}).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(request, timeout=7) as response:
                assert response.status == 204
        expected = int(provider_applied)
        assert receiver.writes == expected

        # Simulates the original process dying with no terminal receipt.
        # Recovery must observe the already-persisted claim after expiry.
        pg.psql(
            "UPDATE public.write_invoke_idempotency "
            "SET lease_expires_at=now()-interval '1 minute' "
            f"WHERE org_id='{ORG}' AND idempotency_key='{key}';"
        )
        service = PgRecoveryClient(pg)
        original = ToolContext(
            settings=SimpleNamespace(), client=service, org_id=ORG,
            actor_id="system:write-recovery", connector_id="conn-a",
        )

        def readback(*, ctx, invoke_action, args):
            assert ctx.org_id == ORG and ctx.connector_id == "conn-a"
            assert invoke_action == "hubspot.contacts.create"
            assert args == {"email": "qa@example.invalid"}
            assert receiver.writes == expected
            if provider_applied:
                return ReconciliationResult(
                    "applied", "requested_values_present",
                    resource_id="contact-qa",
                    lookup_action="hubspot.contacts.search",
                    evidence={"verified": True, "receiver_count": expected},
                )
            return ReconciliationResult(
                "not_applied", "requested_values_absent",
                lookup_action="hubspot.contacts.search",
                evidence={
                    "verified": True,
                    "authoritative_absence": True,
                    "receiver_count": 0,
                    "readback_scope": "isolated_independent_receiver",
                },
            )

        with patch(
            "app.services.write_recovery_service.reconcile_uncertain_write",
            side_effect=readback,
        ) as verify:
            result = process_due_write_recoveries(
                service_client=service,
                context_factory=lambda org, connector: original,
            )
            assert result["seen"] == 1
            assert result["error"] == 0 and result["rejected"] == 0
            assert result["completed" if provider_applied else "not_applied"] == 1
            verify.assert_called_once()
            again = process_due_write_recoveries(
                service_client=service,
                context_factory=lambda org, connector: original,
            )
            assert again["seen"] == 0
        assert receiver.writes == expected
        state = pg.value(
            "SELECT status FROM public.write_invoke_idempotency "
            f"WHERE org_id='{ORG}' AND idempotency_key='{key}';"
        )
        assert state == ("completed" if provider_applied else "failed")
        if provider_applied:
            replay = _json(
                pg, f"public.claim_write_invoke_idempotency("
                f"'{ORG}'::uuid,'{key}','hubspot.contacts.create','test-approval',60)",
            )
            assert replay["outcome"] == "replay"
            assert replay["result"]["verification"]["evidence"]["receiver_count"] == 1
            assert receiver.writes == 1
    finally:
        receiver.close()


@pytest.mark.parametrize("lease_state", ["expired", "reassigned"])
def test_persisted_invalid_lease_blocks_provider_readback(pg, lease_state):
    """Actual SQL lease state must reach Python before external readback."""
    from types import SimpleNamespace
    from unittest.mock import patch
    from app.services.write_recovery_service import recover_uncertain_write
    from tests.db.write_recovery_context_fixture import PgRecoveryClient

    key = "readback-lease-" + lease_state
    pg.psql(f"""INSERT INTO public.write_invoke_idempotency
      (org_id,idempotency_key,invoke_action,status,connector_id,original_args)
      VALUES('{ORG}','{key}','hubspot.contacts.create','uncertain',
        'conn-a','{{"email":"qa@example.invalid"}}'::jsonb);""")
    leased = _json(pg, "coalesce((SELECT row_to_json(x) FROM public.claim_due_write_recoveries(1,60) AS x),'{}'::json)")
    token = leased["recovery_lease_token"]
    pg.psql(f"""UPDATE public.write_invoke_idempotency
      SET recovery_lease_expires_at=now()-interval '1 minute'
      WHERE org_id='{ORG}' AND idempotency_key='{key}';""")
    if lease_state == "reassigned":
        replacement = _json(pg, "coalesce((SELECT row_to_json(x) FROM public.claim_due_write_recoveries(1,60) AS x),'{}'::json)")
        assert replacement["recovery_lease_token"] != token
    service = PgRecoveryClient(pg)
    persisted = service.table("write_invoke_idempotency").select("*").eq(
        "org_id", ORG).eq("idempotency_key", key).limit(1).execute().data[0]
    assert persisted["recovery_lease_expires_at"]
    ctx = SimpleNamespace(client=service, org_id=ORG, connector_id="conn-a")
    with patch("app.services.write_recovery_service.reconcile_uncertain_write") as readback:
        result = recover_uncertain_write(
            ctx=ctx, idempotency_key=key,
            invoke_action="hubspot.contacts.create",
            original_args={"email": "qa@example.invalid"},
            recovery_lease_token=token,
        )
    assert result.state == "rejected"
    assert result.detail == (
        "recovery_lease_expired_or_invalid" if lease_state == "expired"
        else "recovery_lease_mismatch"
    )
    readback.assert_not_called()
    assert pg.value(f"SELECT status FROM public.write_invoke_idempotency WHERE idempotency_key='{key}';") == "uncertain"
