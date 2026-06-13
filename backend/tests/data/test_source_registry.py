"""Tests for data source registry."""
from __future__ import annotations

import pytest

from app.data.source_registry import (
    DATA_SOURCE_TYPES,
    list_source_types,
    validate_connection_config,
)


def test_registry_has_enterprise_coverage() -> None:
    assert len(DATA_SOURCE_TYPES) >= 50
    categories = {spec["category"] for spec in DATA_SOURCE_TYPES.values()}
    assert categories >= {"relational", "warehouse", "nosql", "storage", "api", "saas"}


def test_list_source_types_search() -> None:
    items = list_source_types(search="postgres")
    assert any(item["id"] == "postgresql" for item in items)
    assert all("postgresql" in item["id"] or "postgres" in item["name"].lower() for item in items)


def test_validate_postgresql_requires_host_or_connection_string() -> None:
    errors = validate_connection_config("postgresql", {"username": "u", "password": "p", "database": "db"})
    assert any("Host" in err for err in errors)

    ok = validate_connection_config(
        "postgresql",
        {"connection_string": "postgresql://u:p@localhost:5432/db"},
    )
    assert ok == []


def test_validate_unknown_type() -> None:
    assert validate_connection_config("not-a-real-source", {}) == ["Unknown data source type: not-a-real-source"]
