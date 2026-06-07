from __future__ import annotations

from app.connectors.snowflake_config import normalize_snowflake_config, validate_snowflake_config


def test_snowflake_password_config_valid():
    errors = validate_snowflake_config(
        {
            "account": "xy12345.us-east-1",
            "warehouse": "WH",
            "database": "DB",
            "schema": "PUBLIC",
            "role": "ANALYST",
            "auth_method": "password",
        }
    )
    assert errors == []


def test_snowflake_oauth_not_production_ready():
    errors = validate_snowflake_config(
        {
            "account": "acct",
            "warehouse": "WH",
            "database": "DB",
            "schema": "PUBLIC",
            "role": "ANALYST",
            "auth_method": "oauth",
        }
    )
    assert any("not production-ready" in e for e in errors)
