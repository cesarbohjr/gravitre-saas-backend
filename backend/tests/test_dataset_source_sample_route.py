from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_sample_route_is_read_only_and_does_not_materialize_records():
    source = (ROOT / "app" / "routers" / "training.py").read_text()
    start = source.index('async def sample_dataset_source')
    end = source.index('@router.delete("/datasets/{dataset_id}")', start)
    route = source[start:end]

    assert "adapter.sample(" in route
    assert '"materialized": False' in route
    assert '"recordsCreated": 0' in route
    assert 'table("training_records")' not in route
    assert ".insert(" not in route
    assert ".upsert(" not in route
    assert ".delete(" not in route


def test_sample_route_requires_sample_access_mode():
    source = (ROOT / "app" / "routers" / "training.py").read_text()
    start = source.index('async def sample_dataset_source')
    end = source.index('@router.delete("/datasets/{dataset_id}")', start)
    route = source[start:end]
    assert "DatasetSourceAccessMode.SAMPLE" in route
    assert "not configured for sample access" in route


def test_named_provider_registry_only_exposes_huggingface_in_first_slice():
    source = (ROOT / "app" / "training" / "providers" / "__init__.py").read_text()
    assert "HuggingFaceDatasetAdapter" in source
    assert "unsupported dataset provider" in source
    assert "materialize" not in source.lower()
