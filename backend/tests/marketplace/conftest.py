"""Shared Supabase table mocks for marketplace install tests."""
from __future__ import annotations

from unittest.mock import MagicMock
import uuid

import pytest


def marketplace_table_mock(select_data: list | None = None) -> MagicMock:
    """Mock Supabase table chain; inserts return a synthetic row when select_data is None."""
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.is_.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.insert.return_value = mock
    mock.upsert.return_value = mock

    def execute():
        response = MagicMock(error=None)
        if select_data is not None:
            response.data = select_data
        else:
            response.data = [{"id": str(uuid.uuid4())}]
        return response

    mock.execute.side_effect = execute
    return mock


@pytest.fixture(autouse=True)
def _noop_pack_canvas_materialization(monkeypatch):
    """Install tests assert workflow defs/agents — not canvas node persistence."""
    monkeypatch.setattr(
        "app.marketplace.pack_prewiring.materialize_pack_canvas_graph",
        lambda *args, **kwargs: None,
    )

    """Mock Supabase table chain; inserts return a synthetic row when select_data is None."""
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.is_.return_value = mock
    mock.limit.return_value = mock
    mock.update.return_value = mock
    mock.insert.return_value = mock
    mock.upsert.return_value = mock

    def execute():
        response = MagicMock(error=None)
        if select_data is not None:
            response.data = select_data
        else:
            response.data = [{"id": str(uuid.uuid4())}]
        return response

    mock.execute.side_effect = execute
    return mock
