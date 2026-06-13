"""Tests for source sync service."""
from __future__ import annotations

from app.services.source_sync_service import (
    DEFAULT_SYNC_INTERVAL_SECONDS,
    _is_due,
    _sync_interval_seconds,
    validate_saas_connector_link,
)


def test_sync_interval_defaults() -> None:
    assert _sync_interval_seconds({}) == DEFAULT_SYNC_INTERVAL_SECONDS
    assert _sync_interval_seconds({"syncIntervalSeconds": 120}) == 120


def test_is_due_without_last_sync() -> None:
    from datetime import datetime, timezone

    assert _is_due({"metadata": {}}, now=datetime.now(timezone.utc)) is True


def test_validate_saas_requires_connector_id() -> None:
    class DummyClient:
        def table(self, *_args, **_kwargs):
            return self

        def select(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def execute(self):
            return type("R", (), {"data": []})()

    errors = validate_saas_connector_link(
        DummyClient(),
        "org-1",
        type_id="hubspot",
        config={},
        environment="production",
    )
    assert "Linked connector is required" in errors[0]
