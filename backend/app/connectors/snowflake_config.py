"""Snowflake connector configuration schema (multi auth-method; OAuth not production-ready)."""
from __future__ import annotations

from typing import Any, Literal

SnowflakeAuthMethod = Literal["oauth", "password", "key_pair"]

REQUIRED_SNOWFLAKE_FIELDS = ("account", "warehouse", "database", "schema", "role")


def normalize_snowflake_config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(config or {})
    account = str(cfg.get("account") or cfg.get("snowflake_account") or cfg.get("subdomain") or "").strip()
    out: dict[str, Any] = {
        "account": account,
        "warehouse": str(cfg.get("warehouse") or "").strip(),
        "database": str(cfg.get("database") or "").strip(),
        "schema": str(cfg.get("schema") or "PUBLIC").strip() or "PUBLIC",
        "role": str(cfg.get("role") or "").strip(),
        "auth_method": str(cfg.get("auth_method") or cfg.get("authMethod") or "password").strip().lower(),
    }
    if out["auth_method"] not in {"oauth", "password", "key_pair"}:
        out["auth_method"] = "password"
    return out


def validate_snowflake_config(config: dict[str, Any] | None) -> list[str]:
    """Return list of validation errors (empty if valid placeholder config)."""
    cfg = normalize_snowflake_config(config)
    errors: list[str] = []
    for field in REQUIRED_SNOWFLAKE_FIELDS:
        if not cfg.get(field):
            errors.append(f"snowflake.{field} is required")
    if cfg["auth_method"] == "oauth":
        errors.append("snowflake OAuth connect flow is not production-ready; use password or key_pair")
    return errors


def snowflake_oauth_ready() -> bool:
    """Gate Snowflake OAuth until token exchange + connection test ship."""
    return False
