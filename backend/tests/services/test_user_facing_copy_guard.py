"""Regression: user-facing copy must never leak raw connector catalog action keys."""
from __future__ import annotations

import pytest

from app.services.connector_action_workflows import format_capability_fallback_message
from app.services.execution_envelope import format_not_executable_message, format_operator_response
from app.services.user_facing_copy_guard import (
    RAW_CATALOG_ACTION_KEY,
    assert_no_raw_catalog_action_keys,
    contains_raw_catalog_action_key,
    dedupe_repeated_paragraphs,
    finalize_user_facing_message,
    humanize_catalog_action_key,
)

_SAMPLE_KEYS = (
    "gmail.messages.list",
    "gmail.drafts.create",
    "gmail.messages.send",
    "microsoft365.mail.messages.list",
    "apollo.lists.create",
    "hubspot.contacts.search",
)


def test_humanize_catalog_action_key_never_returns_dotted_id():
    for key in _SAMPLE_KEYS:
        human = humanize_catalog_action_key(key)
        assert not contains_raw_catalog_action_key(human), human
        assert key not in human


def test_format_operator_response_unmapped_intent_no_catalog_dump():
    available = [
        "gmail.messages.list — List messages",
        "gmail.drafts.create — Create draft",
        "gmail.messages.send — Send message",
    ]
    text = format_operator_response(
        intent="Check Stephanie's email",
        status="blocked — no matching catalog action",
        available_actions=available,
        next_step="Tell me whether you want to read, draft, or send mail.",
    )
    assert "gmail." not in text
    for key in _SAMPLE_KEYS:
        assert key not in text
    assert "List messages" in text
    assert "Create draft" in text


def test_format_capability_fallback_message_no_raw_keys():
    text = format_capability_fallback_message(
        integration="gmail",
        intent="Create a list",
        missing_action="gmail.labels.create",
        available_actions=[
            "gmail.messages.list — List messages",
            "gmail.messages.send — Send message",
        ],
    )
    for key in _SAMPLE_KEYS:
        assert key not in text
    assert "List messages" in text


def test_format_not_executable_message_operator_format_scrubs_metadata_actions():
    payload = {
        "reason": "not_implemented",
        "next_step": "Connect Gmail and describe what you want in plain language.",
        "metadata": {
            "operator_format": True,
            "intent": "Send an email",
            "status": "blocked — no matching catalog action",
            "available_actions": ["gmail.messages.send — Send message"],
            "missing_action": "gmail.drafts.create",
            "matched_action": "gmail.messages.list",
        },
    }
    text = format_not_executable_message(payload)
    for key in _SAMPLE_KEYS:
        assert key not in text


def test_assert_no_raw_catalog_action_keys_detects_leak():
    with pytest.raises(AssertionError, match="raw catalog action"):
        assert_no_raw_catalog_action_keys("Try running gmail.messages.list next.")


def test_finalize_user_facing_message_scrubs_catalog_keys():
    cleaned = finalize_user_facing_message("Try running gmail.messages.list next.")
    assert "gmail.messages.list" not in cleaned


def test_dedupe_repeated_paragraphs_sta335():
    dup = (
        "Send email is ready, but it still needs your approval. "
        "Reply **yes** to send, or **cancel** to stop.\n"
        "Send email is ready, but it still needs your approval. "
        "Reply **yes** to send, or **cancel** to stop."
    )
    assert dedupe_repeated_paragraphs(dup).count("Send email is ready") == 1
    assert finalize_user_facing_message(dup).count("Send email is ready") == 1


@pytest.mark.parametrize(
    "message_builder",
    [
        lambda: format_operator_response(
            intent="Email Stephanie",
            status="blocked — action not in catalog",
            missing_action="gmail.messages.send",
            available_actions=["gmail.drafts.create — Create draft"],
        ),
        lambda: format_operator_response(
            intent="Email Stephanie",
            status="blocked — action not matched",
            matched_action="gmail.messages.send",
        ),
    ],
)
def test_all_operator_fallback_variants_pass_guard(message_builder):
    text = message_builder()
    assert_no_raw_catalog_action_keys(text)
