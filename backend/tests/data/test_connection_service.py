"""Tests for connection validation helpers."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.data.connection_service import ConnectionTestError, config_from_encrypted_blob, run_connection_test


@pytest.mark.asyncio
@patch(
    "app.data.connection_service._snowflake_connect",
    side_effect=ConnectionTestError("Snowflake driver is not installed", code="DRIVER_MISSING"),
)
async def test_config_only_driver_pending_for_snowflake(_mock_connect) -> None:
    result = await run_connection_test(
        "snowflake",
        {
            "account": "xy12345.us-east-1",
            "username": "user",
            "password": "pass",
            "warehouse": "WH",
            "database": "DB",
        },
    )
    assert result["success"] is True
    assert result.get("driverPending") is True


@pytest.mark.asyncio
async def test_validation_error_for_missing_fields() -> None:
    with pytest.raises(ConnectionTestError) as exc:
        await run_connection_test("bigquery", {"project_id": "demo"})
    assert exc.value.code == "VALIDATION_ERROR"


def test_config_from_encrypted_blob_json_and_legacy_string() -> None:
    assert config_from_encrypted_blob('{"host":"db","database":"main"}')["host"] == "db"
    assert config_from_encrypted_blob("postgresql://u:p@host/db")["connection_string"].startswith("postgresql://")
