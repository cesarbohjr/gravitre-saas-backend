from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_org_context
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


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
