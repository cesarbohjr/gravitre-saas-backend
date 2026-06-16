"""Unit tests for weekly throughput aggregation."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.config import Settings
from app.metrics.service import weekly_throughput_metrics


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


@patch("app.metrics.service._start_of_week_utc")
def test_weekly_throughput_aggregates_rag_chunks(mock_week_start):
    mock_week_start.return_value = datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc)
    monday_noon = datetime(2026, 6, 8, 12, 0, tzinfo=timezone.utc)

    def table_side_effect(name: str):
        table = MagicMock()
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        if name == "rag_ingest_jobs":
            chain.execute.return_value = SimpleNamespace(
                data=[{"created_at": monday_noon.isoformat(), "chunk_count": 100, "status": "completed"}]
            )
        else:
            chain.execute.return_value = SimpleNamespace(data=[])
        table.select.return_value = chain
        return table

    client = MagicMock()
    client.table.side_effect = table_side_effect

    with patch("app.metrics.service._client", return_value=client):
        result = weekly_throughput_metrics(_settings(), "org-1")

    assert result["days"][0] == {"day": "Mon", "records": 100, "target": result["target"]}
    assert result["target"] > 0
