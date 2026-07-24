"""Tests for connector write intent comprehension."""
from __future__ import annotations

from app.services.chat_write_intent import (
    classify_gmail_write_intent,
    evaluate_connector_tool_proposal,
    is_gmail_send_intent,
)
from app.services.connector_execution_matrix import get_matrix_entry


def test_gmail_send_intent_detects_send_email_phrasing():
    assert is_gmail_send_intent("Send an email via Gmail to demo@example.com")
    assert classify_gmail_write_intent("Send email to a@b.com with subject Hi") == "single_send"
    assert classify_gmail_write_intent("List my Gmail labels") == "none"


def test_mismatch_send_email_vs_batch_modify_clarifies():
    review = evaluate_connector_tool_proposal(
        message='Send email to demo@example.com with subject "Hi" and body "Test"',
        tool_name="gmail_messages_batch",
        invoke_action="gmail.messages.batch",
        args={"message_ids": ["abc"]},
    )
    assert review.action == "clarify"
    assert "Send email" in review.clarify_message
    assert "Batch modify" in review.clarify_message


def test_batch_intent_accepts_batch_tool():
    review = evaluate_connector_tool_proposal(
        message="Batch modify these Gmail message IDs: abc, def",
        tool_name="gmail_messages_batch",
        invoke_action="gmail.messages.batch",
        args={"message_ids": ["abc", "def"]},
    )
    assert review.action == "accept"


def test_unspecified_gmail_write_clarifies_on_advanced_tool():
    review = evaluate_connector_tool_proposal(
        message="Do something with Gmail email",
        tool_name="gmail_messages_batch",
        invoke_action="gmail.messages.batch",
        args={},
    )
    assert review.action == "clarify"
    assert "Send email" in review.clarify_message


def test_gmail_batch_chat_executable_all_tiers():
    entry = get_matrix_entry("gmail", "gmail.messages.batch")
    assert entry is not None
    assert entry.implementation_status != "not_implemented"
    assert entry.chat_executable is True
    assert entry.tier == "v3"


def test_gmail_send_still_chat_executable():
    entry = get_matrix_entry("gmail", "gmail.messages.send")
    assert entry is not None
    assert entry.chat_executable is True
