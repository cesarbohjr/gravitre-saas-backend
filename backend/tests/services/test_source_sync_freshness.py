"""Phase 1: a source health check must not claim a data sync (no last_sync_at write)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import source_sync_service as svc


def test_health_check_records_check_time_not_last_sync_at():
    client = MagicMock()
    settings = SimpleNamespace(encryption_key=None)
    row = {"id": "src-1", "type": "postgresql", "metadata": {}, "status": "connected"}
    with patch.object(svc, "run_connection_test", AsyncMock(return_value={"tables": 3, "records": 10})), patch.object(
        svc, "discover_schema", AsyncMock(return_value={"tableCount": 3})
    ), patch.object(svc, "write_audit_event"):
        result = asyncio.run(
            svc.sync_source_row(client, settings, org_id="org-1", row=row, environment="production", actor_id="u")
        )
    assert result["success"] is True
    final = client.table.return_value.update.call_args_list[-1][0][0]
    assert "last_sync_at" not in final
    assert final["status"] == "connected"
    assert final["metadata"]["lastCheckedAt"]


def test_is_due_uses_last_check_time():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(seconds=30)).isoformat()
    old = (now - timedelta(days=2)).isoformat()
    assert svc._is_due({"metadata": {"lastCheckedAt": recent}, "last_sync_at": old}, now=now) is False
    assert svc._is_due({"metadata": {"lastCheckedAt": old}, "last_sync_at": None}, now=now) is True
    # Rows written before checks were recorded separately keep working.
    assert svc._is_due({"metadata": {}, "last_sync_at": recent}, now=now) is False
