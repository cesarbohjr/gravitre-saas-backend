from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_binding_migration_keeps_provider_neutral_purposes():
    sql = (ROOT.parent / "supabase" / "migrations" / "20260929144607_training_dataset_bindings.sql").read_text()
    for purpose in (
        "reference",
        "benchmark",
        "runtime_retrieval",
        "rag",
        "evaluation",
        "testing",
        "fine_tuning",
        "training",
        "synthetic",
        "agent_benchmarking",
    ):
        assert f"'{purpose}'" in sql
    for target in ("agent", "model", "department", "evaluation", "play", "workflow"):
        assert f"'{target}'" in sql
    assert "huggingface" not in sql.lower()
    assert "training_datasets" in sql


def test_training_router_exposes_binding_api_without_new_dataset_router():
    source = (ROOT / "app" / "routers" / "training.py").read_text()
    assert '/datasets/{dataset_id}/bindings' in source
    assert "training_dataset_bindings" in source
