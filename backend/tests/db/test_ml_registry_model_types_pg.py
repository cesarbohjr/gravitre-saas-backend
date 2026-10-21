"""Registry enum compatibility without weakening runtime status or RLS gates."""
import subprocess

import pytest

from app.ml.base import ModelType
from tests.db.pg_harness import MIGRATIONS, pg_cluster, requires_pg

pytestmark = requires_pg
MIGRATION = MIGRATIONS / "20261020234133_ml_registry_model_type_compatibility.sql"
BOOTSTRAP = """
CREATE TABLE public.trained_models (
  id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_type text NOT NULL CONSTRAINT trained_models_model_type_check
    CHECK (model_type IN ('classifier','fine_tuned_llm','anomaly_detector','forecaster','embedding')),
  status text NOT NULL DEFAULT 'draft' CONSTRAINT trained_models_status_check
    CHECK (status IN ('draft','training','validating','ready','deployed','failed','archived'))
);
ALTER TABLE public.trained_models ENABLE ROW LEVEL SECURITY;
INSERT INTO public.trained_models(model_type) VALUES ('classifier');
"""


def test_all_runtime_types_fit_existing_registry_after_migration():
    with pg_cluster(BOOTSTRAP) as db:
        with pytest.raises(subprocess.CalledProcessError):
            db.psql("INSERT INTO public.trained_models(model_type) VALUES ('regressor')")
        db.psql(MIGRATION.read_text())
        for model_type in ModelType:
            db.psql(f"INSERT INTO public.trained_models(model_type) VALUES ('{model_type.value}')")
        assert db.value("SELECT count(*) FROM public.trained_models") == str(len(ModelType)+1)
        assert db.value("SELECT relrowsecurity FROM pg_class WHERE oid='public.trained_models'::regclass") == "t"
        with pytest.raises(subprocess.CalledProcessError):
            db.psql("INSERT INTO public.trained_models(model_type) VALUES ('invented')")
        with pytest.raises(subprocess.CalledProcessError):
            db.psql("INSERT INTO public.trained_models(model_type,status) VALUES ('classifier','trained')")
