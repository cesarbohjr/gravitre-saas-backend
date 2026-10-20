"""workflow_runs accepts event trigger types the services insert (real PostgreSQL)."""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013070000_workflow_runs_event_trigger_types.sql"
pytestmark = requires_pg

BOOTSTRAP = """
CREATE TABLE public.workflow_runs (id serial PRIMARY KEY, trigger_type text NOT NULL DEFAULT 'manual');
ALTER TABLE public.workflow_runs ADD CONSTRAINT workflow_runs_trigger_type_check
  CHECK (trigger_type IN ('manual', 'schedule', 'rollback', 'webhook', 'api', 'hubspot'));
INSERT INTO public.workflow_runs (trigger_type) VALUES ('manual'), ('hubspot');
"""


@pytest.mark.parametrize("trigger", ["salesforce", "segment", "pagerduty", "freshservice"])
def test_event_trigger_types_insert_after_migration(trigger):
    with pg_cluster(BOOTSTRAP) as pg:
        before = pg.psql(f"INSERT INTO public.workflow_runs (trigger_type) VALUES ('{trigger}');", check=False)
        assert before.returncode != 0 and "workflow_runs_trigger_type_check" in before.stderr
        pg.psql(MIGRATION.read_text())
        pg.psql(f"INSERT INTO public.workflow_runs (trigger_type) VALUES ('{trigger}');")
        bad = pg.psql("INSERT INTO public.workflow_runs (trigger_type) VALUES ('nonsense');", check=False)
        assert bad.returncode != 0
        assert pg.value("SELECT convalidated FROM pg_constraint WHERE conname = 'workflow_runs_trigger_type_check';") == "t"
        pg.psql(MIGRATION.read_text())  # idempotent
