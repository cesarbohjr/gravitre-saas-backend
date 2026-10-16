"""Allowance serialization across assistant and generic writers on real PostgreSQL."""
from __future__ import annotations

import concurrent.futures

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg
from tests.db.test_assistant_usage_atomic_pg import BOOTSTRAP, CALL_1, ORG_A, ORG_B

pytestmark = requires_pg


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(
        BOOTSTRAP,
        (MIGRATIONS / "20261016032039_assistant_usage_atomic.sql").read_text(),
        (MIGRATIONS / "20261016032048_atomic_usage_all_sources.sql").read_text(),
    ) as server:
        yield server


@pytest.fixture(autouse=True)
def _clean(pg):
    pg.psql("TRUNCATE public.usage_tracking, public.overage_usage;")
    yield


def _generic(pg, key="run-1", quantity=8, included=10, metric="ai_credits", org=ORG_A):
    return pg.value(
        "SET ROLE service_role; SELECT public.record_usage_with_overage_atomic("
        f"'{org}', 'production', '{metric}', {quantity}, '2026-09-01', "
        f"'2026-09-30', {included}, '{key}', NULL, NULL, NULL, NULL, "
        "'workflow', 'run-1');"
    )


def _assistant(pg):
    return pg.value(
        "SET ROLE service_role; SELECT public.record_assistant_model_usage("
        f"'{ORG_A}', '{CALL_1}', 8, 10, 'production');"
    )


def test_mixed_writers_share_allowance_and_replay_is_exact(pg):
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        a, b = list(pool.map(lambda f: f(pg), (_generic, _assistant)))
    assert (a, b) == ("inserted", "inserted")
    assert _generic(pg) == "duplicate"
    assert pg.value("SELECT sum(quantity) FROM public.usage_tracking;") == "16"
    assert pg.value("SELECT sum(quantity) FROM public.overage_usage;") == "6"
    assert pg.psql(
        "SET ROLE service_role; SELECT public.record_usage_with_overage_atomic("
        f"'{ORG_A}', 'production', 'ai_credits', 9, '2026-09-01', "
        "'2026-09-30', 10, 'run-1', NULL, NULL, NULL, NULL, 'workflow', 'run-1');",
        check=False,
    ).returncode != 0


def test_workflow_allowance_and_tenant_boundaries(pg):
    assert _generic(pg, "wf-1", 8, 10, "workflow_runs") == "inserted"
    assert _generic(pg, "wf-2", 8, 10, "workflow_runs") == "inserted"
    assert _generic(pg, "wf-1", 8, 10, "workflow_runs", ORG_B) == "inserted"
    assert pg.value(
        f"SELECT sum(quantity) FROM public.overage_usage WHERE org_id='{ORG_A}'"
    ) == "6"
    assert pg.value(
        f"SELECT count(*) FROM public.overage_usage WHERE org_id='{ORG_B}'"
    ) == "0"


def test_grants_and_rollback_on_overage_failure(pg):
    denied = pg.psql(
        "SET ROLE authenticated; SELECT public.record_usage_with_overage_atomic("
        f"'{ORG_A}', 'production', 'ai_credits', 8, '2026-09-01', "
        "'2026-09-30', 10, 'bad');", check=False,
    )
    assert denied.returncode != 0
    assert "permission denied" in (denied.stdout + denied.stderr).lower()
    assert _generic(pg, "first") == "inserted"
    pg.psql("""
CREATE FUNCTION public.reject_generic_overage() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'simulated overage failure'; END $$;
CREATE TRIGGER fail_generic_overage BEFORE INSERT ON public.overage_usage
FOR EACH ROW EXECUTE FUNCTION public.reject_generic_overage();
""")
    try:
        assert pg.psql(
            "SET ROLE service_role; SELECT public.record_usage_with_overage_atomic("
            f"'{ORG_A}', 'production', 'ai_credits', 8, '2026-09-01', "
            "'2026-09-30', 10, 'second', NULL, NULL, NULL, NULL, 'workflow', 'run-1');",
            check=False,
        ).returncode != 0
        assert pg.value("SELECT count(*) FROM public.usage_tracking;") == "1"
    finally:
        pg.psql("DROP TRIGGER fail_generic_overage ON public.overage_usage; "
                "DROP FUNCTION public.reject_generic_overage();")
