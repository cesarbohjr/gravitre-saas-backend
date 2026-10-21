"""Actual additive migration preserves old rows and tenant isolation."""
import subprocess

import pytest

from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg
MIGRATION = MIGRATIONS/'20261021050510_federated_ranker_observation_snapshot.sql'
BOOTSTRAP = """
CREATE TABLE public.rag_chunk_outcomes (
 id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 org_id text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
 outcome_helpful boolean
);
ALTER TABLE public.rag_chunk_outcomes ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_rows ON public.rag_chunk_outcomes USING (org_id = current_user);
INSERT INTO public.rag_chunk_outcomes(org_id) VALUES ('legacy');
"""


def test_actual_snapshot_migration_rejects_incomplete_features_without_backfilling():
    with pg_cluster(BOOTSTRAP) as db:
        db.psql(MIGRATION.read_text())
        assert db.value('SELECT count(*) FROM public.rag_chunk_outcomes WHERE ranker_features IS NULL')=='1'
        assert db.value("SELECT relrowsecurity FROM pg_class WHERE oid='public.rag_chunk_outcomes'::regclass")=='t'
        assert db.value("SELECT count(*) FROM pg_policies WHERE tablename='rag_chunk_outcomes' AND policyname='tenant_rows'")=='1'
        good = """'{"rerank_score":0.7,"rank_position":1,"source_reliability_score":0.6,"source_document_age_days":12}'::jsonb"""
        db.psql(f"INSERT INTO public.rag_chunk_outcomes(org_id,ranker_features,ranker_features_observed_at) VALUES ('org',{good},now())")
        for bad in ("'{}'::jsonb", "'[]'::jsonb", "'null'::jsonb", "NULL"):
            with pytest.raises(subprocess.CalledProcessError):
                db.psql(f"INSERT INTO public.rag_chunk_outcomes(org_id,ranker_features,ranker_features_observed_at) VALUES ('org',{bad},now())")
        with pytest.raises(subprocess.CalledProcessError):
            db.psql(f"INSERT INTO public.rag_chunk_outcomes(org_id,ranker_features,ranker_features_observed_at) VALUES ('org',{good},now()+interval '1 day')")
