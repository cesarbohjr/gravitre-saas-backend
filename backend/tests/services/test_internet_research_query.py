"""Tests for governance-bound internet research query construction."""
from __future__ import annotations

from app.services.internet_research_query import (
    GOVERNANCE_MAX_QUERY_CHARS,
    prepare_internet_research_query,
)


def test_prepare_query_truncates_long_bare_query():
    raw = "x" * 3000
    prepared = prepare_internet_research_query(raw)
    assert len(prepared.query) == GOVERNANCE_MAX_QUERY_CHARS
    assert prepared.was_truncated is True
    assert prepared.context_stripped is False


def test_prepare_query_strips_knowledge_base_context():
    raw = (
        "<knowledge_base>{\"source\": \"Refund policy v3\", \"content\": \"30-day window\"}</knowledge_base>\n"
        "What is the current US federal funds rate?"
    )
    prepared = prepare_internet_research_query(raw)
    assert prepared.context_stripped is True
    assert "Refund policy" not in prepared.query
    assert prepared.query == "What is the current US federal funds rate?"


def test_prepare_query_prefers_explicit_query_line_over_conversation_blob():
    raw = (
        "User: Can you remind me what we said about refunds?\n"
        "Assistant: Refunds are allowed within 30 days.\n"
        "User: Thanks — also check this for me.\n"
        "Query: current US federal funds rate"
    )
    prepared = prepare_internet_research_query(raw)
    assert prepared.context_stripped is True
    assert prepared.query == "current US federal funds rate"
    assert "refund" not in prepared.query.lower()


def test_prepare_query_uses_last_user_turn_when_no_explicit_query():
    raw = (
        "User: earlier you mentioned our refund policy\n"
        "Assistant: yes, 30 days\n"
        "User: What is the current US federal funds rate?"
    )
    prepared = prepare_internet_research_query(raw)
    assert prepared.context_stripped is True
    assert prepared.query == "What is the current US federal funds rate?"
    assert "refund" not in prepared.query.lower()


def test_prepare_query_vendor_payload_never_exceeds_governance_cap():
    context = "<knowledge_base>" + ("internal " * 500) + "</knowledge_base>\n"
    tail = "y" * 2500
    prepared = prepare_internet_research_query(context + tail)
    meta = prepared.to_metadata()
    assert len(meta["query_sent"]) <= GOVERNANCE_MAX_QUERY_CHARS
    assert len(prepared.query) <= GOVERNANCE_MAX_QUERY_CHARS
