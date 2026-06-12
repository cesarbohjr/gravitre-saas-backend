from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.services.training_service import (
    is_missing_column_error,
    is_schema_unavailable_error,
    list_custom_instructions,
    list_training_datasets,
    list_training_jobs,
    list_workflow_agents,
)


def test_is_schema_unavailable_error_detects_missing_table():
    assert is_schema_unavailable_error(Exception('relation "training_datasets" does not exist'))
    assert is_schema_unavailable_error(Exception("Could not find the table public.agents in the schema cache"))
    assert not is_schema_unavailable_error(Exception("column agents.trained_model_id does not exist"))
    assert is_missing_column_error(Exception("column agents.trained_model_id does not exist"))


def test_list_training_datasets_returns_empty_when_table_missing():
    client = MagicMock()
    response = SimpleNamespace(data=None, error=Exception('relation "training_datasets" does not exist'))
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = response
    assert list_training_datasets(client, "org-1") == []


def test_list_workflow_agents_falls_back_without_trained_model_column():
    client = MagicMock()
    table = client.table.return_value

    def _select(columns: str):
        chain = MagicMock()
        if "trained_model_id" in columns:
            chain.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
                data=None,
                error=Exception("column agents.trained_model_id does not exist"),
            )
        else:
            chain.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
                data=[{"id": "a1", "name": "RevOps", "role": "REVENUE_OPS", "model": "gpt-4.1-mini", "status": "active"}],
                error=None,
            )
        return chain

    table.select.side_effect = _select
    agents = list_workflow_agents(client, "org-1")
    assert len(agents) == 1
    assert agents[0]["name"] == "RevOps"
    assert agents[0]["trainedModelId"] is None


def test_list_custom_instructions_enriches_agent_name():
    client = MagicMock()

    def _table(name: str):
        mock = MagicMock()
        if name == "custom_instructions":
            mock.select.return_value.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
                data=[
                    {
                        "id": "i1",
                        "agent_id": "a1",
                        "name": "Tone",
                        "content": "Be concise",
                        "is_active": True,
                        "created_at": "2026-01-01",
                        "updated_at": "2026-01-01",
                    }
                ],
                error=None,
            )
        elif name == "agents":
            mock.select.return_value.eq.return_value.in_.return_value.execute.return_value = SimpleNamespace(
                data=[{"id": "a1", "name": "RevOps Agent"}],
                error=None,
            )
        return mock

    client.table.side_effect = _table
    rows = list_custom_instructions(client, "org-1")
    assert rows[0]["agent_name"] == "RevOps Agent"


def test_list_training_jobs_returns_empty_on_schema_error():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.side_effect = Exception(
        "PGRST205: Could not find the table"
    )
    assert list_training_jobs(client, "org-1") == []
