"""Phase 5 goal / work / job links against real PostgreSQL."""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

MIGRATION = MIGRATIONS / "20261012050000_goal_work_links.sql"
ORG = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
GOAL = "aaaaaaaa-0000-4000-8000-000000000001"
OTHER_GOAL = "aaaaaaaa-0000-4000-8000-000000000002"
ENTITY = "eeeeeeee-0000-4000-8000-000000000001"
OTHER_ENTITY = "eeeeeeee-0000-4000-8000-000000000002"

BOOTSTRAP_SQL = f"""
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.goals (id uuid PRIMARY KEY, org_id uuid NOT NULL REFERENCES public.organizations(id));
CREATE TABLE public.org_business_entities (id uuid PRIMARY KEY, org_id uuid NOT NULL REFERENCES public.organizations(id));
CREATE TABLE public.work_objects (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  title text NOT NULL,
  status text NOT NULL DEFAULT 'identified' CHECK (
    status IN ('identified','planned','in_progress','awaiting_approval','blocked','completed','failed','archived')
  )
);
CREATE TABLE public.agent_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id),
  status text NOT NULL DEFAULT 'queued'
);
INSERT INTO public.organizations VALUES ('{ORG}'), ('{OTHER}');
INSERT INTO public.goals VALUES ('{GOAL}', '{ORG}'), ('{OTHER_GOAL}', '{OTHER}');
INSERT INTO public.org_business_entities VALUES ('{ENTITY}', '{ORG}'), ('{OTHER_ENTITY}', '{OTHER}');
INSERT INTO public.work_objects (org_id, title, status) VALUES ('{ORG}', 'existing', 'completed');
"""


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


def _fails(pg, sql: str) -> str:
    res = pg.psql(sql, check=False)
    assert res.returncode != 0
    return res.stderr


def test_migration_is_idempotent_and_keeps_existing_rows(pg):
    pg.psql(MIGRATION.read_text())
    assert pg.value("SELECT count(*) FROM public.work_objects WHERE title = 'existing';") == "1"


def test_proposed_status_and_same_org_links(pg):
    wid = pg.value(
        f"INSERT INTO public.work_objects (org_id, title, status, goal_id, business_entity_id)"
        f" VALUES ('{ORG}', 'p', 'proposed', '{GOAL}', '{ENTITY}') RETURNING id;"
    ).splitlines()[0]
    assert "is not in org" in _fails(
        pg, f"INSERT INTO public.work_objects (org_id, title, goal_id) VALUES ('{ORG}', 'x', '{OTHER_GOAL}');"
    )
    assert "is not in org" in _fails(
        pg, f"INSERT INTO public.work_objects (org_id, title, business_entity_id) VALUES ('{ORG}', 'x', '{OTHER_ENTITY}');"
    )
    _fails(pg, f"INSERT INTO public.work_objects (org_id, title, status) VALUES ('{ORG}', 'x', 'bogus');")
    pg.psql(f"INSERT INTO public.agent_jobs (org_id, goal_id, work_object_id) VALUES ('{ORG}', '{GOAL}', '{wid}');")
    assert "is not in org" in _fails(
        pg, f"INSERT INTO public.agent_jobs (org_id, work_object_id) VALUES ('{OTHER}', '{wid}');"
    )


def test_deleting_a_goal_unlinks_instead_of_deleting_work(pg):
    goal = "aaaaaaaa-0000-4000-8000-0000000000ff"
    pg.psql(f"INSERT INTO public.goals VALUES ('{goal}', '{ORG}');")
    pg.psql(f"INSERT INTO public.work_objects (org_id, title, goal_id) VALUES ('{ORG}', 'linked', '{goal}');")
    pg.psql(f"INSERT INTO public.agent_jobs (org_id, goal_id) VALUES ('{ORG}', '{goal}');")
    pg.psql(f"DELETE FROM public.goals WHERE id = '{goal}';")
    assert pg.value("SELECT goal_id IS NULL FROM public.work_objects WHERE title = 'linked';") == "t"
    assert pg.value(f"SELECT count(*) FROM public.agent_jobs WHERE goal_id = '{goal}';") == "0"
