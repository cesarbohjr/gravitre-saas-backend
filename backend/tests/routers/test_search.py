"""Tests for semantic search helpers and route."""
from __future__ import annotations

from unittest.mock import MagicMock

from app.routers import search as search_router


def test_search_tokens_strips_stopwords():
    tokens = search_router._search_tokens("failed runs in production today")
    assert "failed" in tokens
    assert "runs" in tokens
    assert "in" not in tokens
    assert "today" not in tokens


def test_parse_search_intent_failed_runs():
    intent = search_router._parse_search_intent("failed runs in production today")
    assert intent["run_status"] == "failed"
    assert intent["environment"] == "production"
    assert intent["today_only"] is True
    assert intent["entity_focus"] == "run"


def test_parse_search_intent_connector_sync_errors():
    intent = search_router._parse_search_intent("connectors with sync errors")
    assert intent["connector_issue"] is True
    assert intent["entity_focus"] == "connector"


def test_parse_search_intent_hubspot_workflows():
    intent = search_router._parse_search_intent("workflows using HubSpot")
    assert intent["vendor"] == "hubspot"
    assert intent["entity_focus"] == "workflow"


def test_parse_search_intent_finance_agents():
    intent = search_router._parse_search_intent("agents active in finance")
    assert intent["department"] == "finance"
    assert intent["entity_focus"] == "agent"


def test_or_ilike_quotes_spaces():
    clause = search_router._or_ilike(["name", "description"], "hub spot")
    assert clause is not None
    assert 'name.ilike."%hub spot%"' in clause


def test_compute_score_keyword_overlap():
    score = search_router._compute_score(
        "failed runs in production today",
        "Invoice retry run",
        "Status failed in production",
        tokens=["failed", "runs", "production"],
    )
    assert score > 0.6
