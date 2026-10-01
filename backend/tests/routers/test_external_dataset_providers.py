from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context
from app.main import app

client = TestClient(app, raise_server_exceptions=False)
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "user-1",
        "email": "user@example.com",
    }
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    yield
    app.dependency_overrides.clear()


def test_external_dataset_provider_list_is_read_only():
    with patch(
        "app.routers.training.list_external_dataset_providers",
        return_value=[
            {
                "id": "huggingface",
                "label": "Hugging Face",
                "capabilities": ["search", "inspect", "reference"],
                "auth": "optional_token",
                "materialization": "explicit_only",
                "notes": "Public metadata only",
            }
        ],
    ):
        response = client.get("/api/training/external-datasets/providers")
    assert response.status_code == 200
    body = response.json()
    assert body["mutation"] is False
    assert body["materialization"] == "explicit_only"
    assert body["providers"][0]["id"] == "huggingface"


def test_external_dataset_search_does_not_materialize():
    with patch(
        "app.routers.training.search_external_datasets",
        return_value=[
            {
                "provider": "huggingface",
                "dataset_id": "org/example",
                "name": "example",
                "author": "org",
                "description": None,
                "tags": [],
                "downloads": 10,
                "likes": 1,
                "private": False,
                "gated": False,
                "reference_url": "https://huggingface.co/datasets/org/example",
            }
        ],
    ):
        response = client.get(
            "/api/training/external-datasets/search",
            params={"provider": "huggingface", "q": "example"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["mutation"] is False
    assert body["count"] == 1


def test_external_dataset_inspect_preserves_metadata_only_truth():
    with patch(
        "app.routers.training.inspect_external_dataset",
        return_value={
            "provider": "huggingface",
            "dataset_id": "org/example",
            "materialized": False,
            "materializationAllowed": True,
            "truthRule": "Inspection is metadata-only.",
        },
    ):
        response = client.get(
            "/api/training/external-datasets/inspect",
            params={"provider": "huggingface", "datasetId": "org/example"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["mutation"] is False
    assert body["materialized"] is False
    assert body["dataset"]["materialized"] is False


def test_external_dataset_inspect_does_not_bypass_gated_access():
    with patch(
        "app.routers.training.inspect_external_dataset",
        side_effect=PermissionError("Dataset is private or gated"),
    ):
        response = client.get(
            "/api/training/external-datasets/inspect",
            params={"provider": "huggingface", "datasetId": "private/example"},
        )
    assert response.status_code == 403


def test_external_reference_mutations_are_admin_gated_in_router_source():
    source = (ROOT / "app" / "routers" / "training.py").read_text()
    assert '@router.post("/external-datasets/references"' in source
    assert 'Depends(require_admin)' in source
    assert '@router.delete("/external-datasets/references/{reference_id}")' in source


def test_external_reference_migration_is_tenant_scoped_and_non_materializing():
    migration = (
        ROOT.parent
        / "supabase"
        / "migrations"
        / "20260929211911_external_dataset_references.sql"
    ).read_text()
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "organization_members" in migration
    assert "access_mode" in migration
    assert "reference" in migration
    assert "sample" in migration
    assert "index" in migration
    lowered = migration.lower()
    assert "materialized boolean" not in lowered
    assert "materialized_at" not in lowered
    assert "'materialize'" not in lowered


def test_external_reference_metadata_rejects_secret_markers():
    from app.routers.training import _require_safe_external_dataset_metadata

    unsafe = (
        {"token": "secret"},
        {"nested": {"api_key": "secret"}},
        {"url": "https://example.test/data?token=secret"},
        {"authorizationHeader": "Bearer secret"},
    )
    for metadata in unsafe:
        try:
            _require_safe_external_dataset_metadata(metadata)
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 400
        else:
            raise AssertionError(f"expected secret metadata refusal: {metadata}")


def test_external_reference_metadata_allows_normal_provider_metadata():
    from app.routers.training import _require_safe_external_dataset_metadata

    _require_safe_external_dataset_metadata(
        {
            "reference_url": "https://huggingface.co/datasets/org/example",
            "tags": ["finance", "benchmark"],
            "card": {"language": "en", "license": "apache-2.0"},
        }
    )
