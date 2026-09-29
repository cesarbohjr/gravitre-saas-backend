from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dataset_source_schema_is_tenant_scoped_and_secret_free():
    migration = (
        ROOT.parent
        / "supabase"
        / "migrations"
        / "20260929173500_training_dataset_sources.sql"
    ).read_text()
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "organization_members" in migration
    assert "org_id" in migration
    assert "client_secret" not in migration
    assert "access_token" not in migration
    assert "refresh_token" not in migration


def test_dataset_source_layer_has_no_provider_specific_adapter():
    service = (ROOT / "app" / "services" / "dataset_source_service.py").read_text()
    assert "huggingface" not in service.lower()
    assert "kaggle" not in service.lower()
    assert "download" not in service.lower()


def test_dataset_source_mutation_requires_admin():
    router = (ROOT / "app" / "routers" / "training.py").read_text()
    marker = '@router.post("/datasets/{dataset_id}/sources"'
    start = router.index(marker)
    end = router.index('@router.delete("/datasets/{dataset_id}")', start)
    block = router[start:end]
    assert "Depends(require_admin)" in block
    assert "materializationAutomatic" in router
