"""model_calls run/turn attribution migration (real PostgreSQL)."""
from __future__ import annotations

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

MIGRATION = MIGRATIONS / "20261013080000_model_calls_run_attribution.sql"
pytestmark = requires_pg

BOOTSTRAP = """
CREATE TABLE public.workflow_runs (id uuid PRIMARY KEY);
CREATE TABLE public.model_calls (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL, cost_usd numeric(10,6));
INSERT INTO public.model_calls (org_id, cost_usd) VALUES ('00000000-0000-0000-0000-000000000001', 0.01);
INSERT INTO public.workflow_runs VALUES ('00000000-0000-0000-0000-0000000000aa');
"""


def test_columns_fk_and_indexes_and_existing_rows_untouched():
    with pg_cluster(BOOTSTRAP) as pg:
        pg.psql(MIGRATION.read_text())
        assert pg.value("SELECT count(*) FROM public.model_calls WHERE run_id IS NULL AND turn_id IS NULL;") == "1"
        pg.psql(
            "INSERT INTO public.model_calls (org_id, cost_usd, run_id, turn_id) VALUES "
            "('00000000-0000-0000-0000-000000000001', 0.02, '00000000-0000-0000-0000-0000000000aa', 'msg-1');"
        )
        bad = pg.psql(
            "INSERT INTO public.model_calls (org_id, run_id) VALUES "
            "('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000bb');",
            check=False,
        )
        assert bad.returncode != 0 and "model_calls_run_id_fkey" in bad.stderr
        # Deleting a run keeps its cost rows, unattributed.
        pg.psql("DELETE FROM public.workflow_runs;")
        assert pg.value("SELECT count(*) FROM public.model_calls;") == "2"
        assert pg.value("SELECT count(*) FROM public.model_calls WHERE run_id IS NOT NULL;") == "0"
        assert pg.value("SELECT convalidated FROM pg_constraint WHERE conname = 'model_calls_run_id_fkey';") == "t"
        idx = pg.value(
            "SELECT string_agg(indexname, ',' ORDER BY indexname) FROM pg_indexes WHERE tablename = 'model_calls' "
            "AND indexname LIKE 'idx_model_calls_%';"
        )
        assert idx == "idx_model_calls_org_turn,idx_model_calls_run_id"
        pg.psql(MIGRATION.read_text())  # idempotent
