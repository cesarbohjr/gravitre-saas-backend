"""Phase 6 prediction outcome columns against real PostgreSQL."""
from __future__ import annotations

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg

MIGRATION = MIGRATIONS / "20261012060000_model_prediction_outcomes.sql"
ORG = "11111111-1111-4111-8111-111111111111"
MODEL = "33333333-3333-4333-8333-333333333333"

BOOTSTRAP_SQL = f"""
CREATE TABLE public.organizations (id uuid PRIMARY KEY);
CREATE TABLE public.trained_models (id uuid PRIMARY KEY);
CREATE TABLE public.model_predictions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  model_id uuid NOT NULL REFERENCES public.trained_models(id) ON DELETE CASCADE,
  version integer NOT NULL,
  input_hash text NOT NULL,
  prediction jsonb NOT NULL,
  latency_ms integer,
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO public.organizations VALUES ('{ORG}');
INSERT INTO public.trained_models VALUES ('{MODEL}');
INSERT INTO public.model_predictions (org_id, model_id, version, input_hash, prediction)
  VALUES ('{ORG}', '{MODEL}', 1, 'h', '{{}}');
"""

INSERT = (
    "INSERT INTO public.model_predictions (org_id, model_id, version, input_hash, prediction, {cols})"
    f" VALUES ('{ORG}', '{MODEL}', 1, 'h', jsonb_build_object(), {{vals}});"
)


@pytest.fixture(scope="module")
def pg():
    with pg_cluster(BOOTSTRAP_SQL, MIGRATION.read_text()) as server:
        yield server


def test_existing_rows_become_unlabeled_and_migration_is_idempotent(pg):
    pg.psql(MIGRATION.read_text())
    assert pg.value("SELECT label_status FROM public.model_predictions WHERE input_hash = 'h' LIMIT 1;") == "unlabeled"


def test_pending_needs_subject_and_horizon(pg):
    ok = INSERT.format(cols="label_status, subject_type, subject_id, horizon_days", vals="'pending', 'customer', 'c1', 90")
    pg.psql(ok)
    for cols, vals in (
        ("label_status", "'pending'"),
        ("label_status, subject_type, subject_id, horizon_days", "'pending', 'customer', 'c1', 0"),
        ("label_status", "'guessed'"),
        ("label_status, subject_type, subject_id, horizon_days", "'resolved', 'customer', 'c1', 90"),
    ):
        assert pg.psql(INSERT.format(cols=cols, vals=vals), check=False).returncode != 0
    resolved = INSERT.format(
        cols="label_status, subject_type, subject_id, horizon_days, outcome_label, outcome_source",
        vals="'resolved', 'customer', 'c1', 90, 'churned', 'agent_action_outcomes'",
    )
    pg.psql(resolved)
