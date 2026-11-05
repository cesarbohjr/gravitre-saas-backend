"""PR605: v2 run-status migration tests against isolated PostgreSQL.

No production database calls. The test creates minimal workflow/run tables and
applies the exact versioned migration under test.
"""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg
MIGRATION = MIGRATIONS / "20261105090000_run_status_contract_v2.sql"

ORG = "11111111-1111-4111-8111-111111111111"
RUN = "22222222-2222-4222-8222-222222222222"

BOOTSTRAP = """
CREATE TABLE public.workflow_runs (
  id uuid PRIMARY KEY, org_id uuid NOT NULL, workflow_id uuid,
  status text NOT NULL, approval_status text, trigger_type text,
  run_type text, run_hash text, environment text,
  created_at timestamptz DEFAULT now(), completed_at timestamptz,
  error_message text
);
CREATE TABLE public.runs (
  id uuid PRIMARY KEY, org_id uuid NOT NULL, workflow_id uuid,
  status text NOT NULL, trigger text, approval_status text,
  started_at timestamptz, completed_at timestamptz,
  error_message text, metadata jsonb DEFAULT '{}'::jsonb,
  updated_at timestamptz DEFAULT now(),
  CONSTRAINT runs_status_check CHECK (
    status IN ('queued', 'pending', 'running', 'completed', 'failed',
      'cancelled', 'needs_approval')
  )
);
CREATE TRIGGER trg_mirror_workflow_run_status
AFTER INSERT OR UPDATE ON public.workflow_runs
FOR EACH ROW EXECUTE FUNCTION public.mirror_workflow_run_status_to_contract();
"""


@pytest.fixture
def pg():
    # The trigger is created after the v2 function, on the isolated fixture DB.
    no_trigger, trigger = BOOTSTRAP.split("CREATE TRIGGER trg_mirror_workflow_run_status")
    with pg_cluster(no_trigger, MIGRATION.read_text(),
                    "CREATE TRIGGER trg_mirror_workflow_run_status" + trigger) as server:
        yield server


@pytest.mark.parametrize("source,expected", [
    ("completed", "completed"), ("partial_success", "partial_success"),
    ("flagged_for_review", "flagged_for_review"), ("failed", "failed"),
    ("pending_approval", "needs_approval"), ("verifying", "running"),
    ("verification_inconclusive", "failed"), ("paused", "paused"),
])
def test_v2_status_preserved_and_versioned(pg, source, expected):
    pg.psql(f"""
    INSERT INTO public.workflow_runs (id, org_id, status)
    VALUES ('{RUN}', '{ORG}', '{source}');
    """)
    assert pg.value(f"SELECT status FROM public.runs WHERE id='{RUN}'") == expected
    assert pg.value(f"SELECT metadata->>'execution_lifecycle' FROM public.runs WHERE id='{RUN}'") == source
    assert pg.value(f"SELECT metadata->>'status_contract_version' FROM public.runs WHERE id='{RUN}'") == "2"


def test_v2_update_transitions_are_atomic(pg):
    pg.psql(f"INSERT INTO public.workflow_runs (id,org_id,status) VALUES ('{RUN}','{ORG}','running')")
    pg.psql(f"UPDATE public.workflow_runs SET status='flagged_for_review' WHERE id='{RUN}'")
    assert pg.value(f"SELECT status FROM public.runs WHERE id='{RUN}'") == "flagged_for_review"
    pg.psql(f"UPDATE public.workflow_runs SET status='partial_success' WHERE id='{RUN}'")
    assert pg.value(f"SELECT status FROM public.runs WHERE id='{RUN}'") == "partial_success"


def test_unknown_status_fails_closed_without_changing_either_table(pg):
    pg.psql(f"INSERT INTO public.workflow_runs (id,org_id,status) VALUES ('{RUN}','{ORG}','running')")
    failed = pg.psql(f"UPDATE public.workflow_runs SET status='invented_status' WHERE id='{RUN}'", check=False)
    assert failed.returncode != 0
    assert pg.value(f"SELECT status FROM public.workflow_runs WHERE id='{RUN}'") == "running"
    assert pg.value(f"SELECT status FROM public.runs WHERE id='{RUN}'") == "running"


def test_failed_mirror_constraint_does_not_commit_workflow_update(pg):
    pg.psql("ALTER TABLE public.runs ADD CONSTRAINT reject_review CHECK (status <> 'flagged_for_review')")
    result = pg.psql(
        f"INSERT INTO public.workflow_runs (id,org_id,status) VALUES ('{RUN}','{ORG}','flagged_for_review')",
        check=False,
    )
    assert result.returncode != 0
    assert pg.value("SELECT count(*) FROM public.workflow_runs") == "0"
    assert pg.value("SELECT count(*) FROM public.runs") == "0"


def test_migration_reapply_is_idempotent(pg):
    pg.psql(MIGRATION.read_text())
    assert pg.value("SELECT count(*) FROM pg_constraint WHERE conname='runs_status_check'") == "1"
