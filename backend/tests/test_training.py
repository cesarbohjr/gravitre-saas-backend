"""Training hub API regression tests (BUILD/INSIGHTS audit spec)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, table_client


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


@patch("app.routers.training.create_client")
@patch("app.routers.training.list_training_datasets", return_value=[])
def test_dataset_list_empty(_mock_list, mock_create):
    mock_create.return_value = table_client({})
    authenticate()
    response = client.get("/api/training/datasets")
    assert response.status_code == 200
    assert response.json()["datasets"] == []


@patch("app.routers.training.create_client")
def test_dataset_created(mock_create):
    insert_chain = chain_mock(
        data=[
            {
                "id": "ds-1",
                "name": "Sales pack",
                "type": "examples",
                "status": "processing",
                "record_count": 0,
                "created_by": "user-1",
                "created_at": "2026-06-07T00:00:00+00:00",
                "updated_at": "2026-06-07T00:00:00+00:00",
            }
        ]
    )
    sb = MagicMock()
    table = MagicMock()
    table.insert.return_value = insert_chain
    sb.table.return_value = table
    mock_create.return_value = sb

    authenticate()
    response = client.post(
        "/api/training/datasets",
        json={"name": "Sales pack", "type": "examples", "description": "Starter"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Sales pack"


@patch("app.routers.training.create_client")
def test_example_added_to_dataset(mock_create):
    records_chain = chain_mock(data=[{"id": "rec-1"}])
    rpc_chain = chain_mock(data=[{"record_count": 1}])
    sb = MagicMock()

    def _table(name: str):
        table = MagicMock()
        if name == "training_records":
            table.insert.return_value = records_chain
        return table

    sb.table.side_effect = _table
    sb.rpc.return_value = rpc_chain
    mock_create.return_value = sb

    authenticate()
    response = client.post(
        "/api/training/datasets/ds-1/records",
        json={"records": [{"input": "hello", "expected_output": "world"}]},
    )
    assert response.status_code == 200
    assert response.json()["added"] == 1


@patch("app.routers.training.enqueue_training_job", new_callable=AsyncMock)
@patch("app.routers.training.create_client")
def test_training_job_queued(mock_create, mock_enqueue):
    mock_enqueue.return_value = None
    job_chain = chain_mock(
        data=[
            {
                "id": "job-1",
                "dataset_id": "ds-1",
                "status": "queued",
                "model_base": "gpt-4.1-mini",
                "progress": 0,
                "metrics": {},
                "created_at": "2026-06-07T00:00:00+00:00",
            }
        ]
    )
    sb = MagicMock()
    table = MagicMock()
    table.insert.return_value = job_chain
    sb.table.return_value = table
    mock_create.return_value = sb

    authenticate()
    response = client.post(
        "/api/training/jobs",
        json={"dataset_id": "ds-1", "model_base": "gpt-4.1-mini"},
    )
    assert response.status_code == 201
    mock_enqueue.assert_awaited_once()


@patch("app.routers.training.create_client")
@patch("app.routers.training.list_custom_instructions", return_value=[])
def test_instructions_crud(_mock_list, mock_create):
    insert_chain = chain_mock(
        data=[
            {
                "id": "ins-1",
                "name": "Tone",
                "content": "Be concise.",
                "agent_id": None,
                "is_active": True,
                "created_at": "2026-06-07T00:00:00+00:00",
            }
        ]
    )
    sb = MagicMock()
    table = MagicMock()
    table.insert.return_value = insert_chain
    sb.table.return_value = table
    mock_create.return_value = sb

    authenticate()
    list_response = client.get("/api/training/instructions")
    assert list_response.status_code == 200

    create_response = client.post(
        "/api/training/instructions",
        json={"name": "Tone", "content": "Be concise."},
    )
    assert create_response.status_code == 201
    assert create_response.json()["name"] == "Tone"
