"""PART 17 — connector alias resolution."""
from __future__ import annotations

import pytest

from app.services.connector_semantic_registry import (
    resolve_all_connectors_from_text,
    resolve_connector_from_text,
)


@pytest.mark.parametrize(
    "message,expected",
    [
        ("Tell me about my GA4 website traffic.", "google_analytics"),
        ("How is Google Analytics looking?", "google_analytics"),
        ("show my google analytics traffic", "google_analytics"),
        ("google_analytics reports", "google_analytics"),
        ("What happened to website traffic?", None),
        ("show traffic from analytics", None),
    ],
)
def test_ga4_semantic_resolution(message: str, expected: str | None) -> None:
    assert resolve_connector_from_text(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "GA4",
        "Google Analytics",
        "Google Analytics 4",
        "google analytics",
        "google_analytics",
        "GA",
    ],
)
def test_ga4_aliases_resolve(message: str) -> None:
    assert resolve_connector_from_text(f"show my {message} traffic") == "google_analytics"


def test_gsc_alias() -> None:
    assert resolve_connector_from_text("pull GSC performance") == "google_search_console"


def test_qbo_alias() -> None:
    assert resolve_connector_from_text("sync QBO invoices") == "quickbooks"
