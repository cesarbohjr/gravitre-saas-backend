"""Module D — Gravitree Voice Layer unit tests."""
from __future__ import annotations

import pytest

from app.services.gravitree_voice import (
    CHEV_TERMS,
    GRAVITREE_VOICE_RULES,
    HOUSE_PHRASING,
    VOICE_SECTION_HEADER,
    apply_voice,
    chev_term,
    domain_focus_section,
    format_operator_message,
    format_outcome_digest,
    humor_permitted,
    voice_system_prompt_section,
)


def test_voice_section_contains_chev_and_core_traits():
    section = voice_system_prompt_section()
    assert section.startswith(VOICE_SECTION_HEADER)
    assert "Connected" in section
    assert "Healthy" in section
    assert "Executable" in section
    assert "Verified" in section
    assert "I think" in section
    assert "over-apologize" in section or "Never over-apologize" in section
    assert "Confidence register" in section
    assert "Humor budget" in section
    assert HOUSE_PHRASING["insufficient_info"] in section
    assert len(GRAVITREE_VOICE_RULES) >= 8


def test_apply_voice_idempotent():
    base = "ROLE: Help the user manage Agents."
    once = apply_voice(base)
    twice = apply_voice(once)
    assert once.count(VOICE_SECTION_HEADER) == 1
    assert twice.count(VOICE_SECTION_HEADER) == 1
    assert once == twice


def test_apply_voice_strips_legacy_voice_block():
    legacy = (
        "You are Gravitre AI.\n"
        "VOICE: Write like a trusted operator in a live chat — warm, direct.\n"
        "OUTPUT: Lead with the answer."
    )
    out = apply_voice(legacy)
    assert "VOICE:" not in out
    assert out.count(VOICE_SECTION_HEADER) == 1
    assert "OUTPUT: Lead with the answer." in out


def test_chev_term_canonical():
    assert chev_term("connected") == "Connected"
    assert chev_term("HEALTHY") == "Healthy"
    assert chev_term("executable") == "Executable"
    assert chev_term("verified") == "Verified"
    assert set(CHEV_TERMS) >= {"connected", "healthy", "executable", "verified"}


def test_format_tool_error_uses_connected_vocab():
    msg = format_operator_message(
        "tool_error",
        error_code="connector_not_connected",
        integration="slack",
    )
    assert "Connected" in msg
    assert "Slack" in msg


def test_format_pending_plan_cancelled():
    assert "Cancelled" in format_operator_message("pending_plan_cancelled")


def test_domain_focus_never_replaces_voice_header():
    section = domain_focus_section("Focus on pipeline and conversion.")
    assert section.startswith("## Domain focus")
    assert VOICE_SECTION_HEADER not in section


def test_notification_run_title_body():
    title = format_operator_message(
        "notification_run_title", status="failed", source="chat"
    )
    assert "failed" in title.lower()
    body = format_operator_message(
        "notification_run_body",
        status="completed",
        verified_summary="List created in HubSpot",
    )
    assert "List created" in body


def test_notification_failure_body_uses_blocked_register():
    body = format_operator_message(
        "notification_run_body",
        status="failed",
        error_summary="step blew up",
    )
    assert body.startswith("Blocked.")
    assert "Next:" in body


def test_format_confidence_for_voice_labels_estimates():
    from app.services.gravitree_voice import format_confidence_for_voice

    text = format_confidence_for_voice(0.72, is_estimate=True)
    assert text.startswith("Estimate —")
    assert "72%" in text


def test_format_operator_message_intercepts_numeric_confidence():
    text = format_operator_message("success_win", confidence=0.9, confidence_is_estimate=True)
    assert text.startswith("Estimate —")
    assert "90%" in text


def test_failure_alert_kinds():
    title = format_operator_message("failure_alert_title", label="gmail", repeated=True)
    assert "Repeated" in title and "gmail" in title
    body = format_operator_message(
        "failure_alert_body", blocker="auth expired", failure_count=3
    )
    assert body.startswith("Blocked.")


def test_connector_connect_to_run_house_style():
    msg = format_operator_message(
        "connector_connect_to_run",
        integration="slack",
        confidence_register="blocked",
    )
    assert "Connect Slack" in msg
    assert "/connectors" in msg
    assert "in Gravitre" not in msg


def test_canvas_write_blocked_kind():
    msg = format_operator_message("canvas_write_blocked", allow_humor=True)
    assert "Write blocked" in msg
    assert humor_permitted(kind="canvas_write_blocked", allow_humor=True) is False


def test_humor_forbidden_on_write_approval():
    assert humor_permitted(kind="write_approval", allow_humor=True) is False
    assert humor_permitted(kind="success_win", allow_humor=True) is True
    assert humor_permitted(kind="success_win", allow_humor=False) is False


def test_success_win_humor_budget():
    sober = format_operator_message("success_win", allow_humor=False)
    light = format_operator_message("success_win", allow_humor=True)
    assert sober == HOUSE_PHRASING["success_win"]
    assert light == HOUSE_PHRASING["success_win_light"]


def test_estimate_register_prefix():
    msg = format_operator_message(
        "estimate",
        detail="pipeline is thinning this week.",
        confidence_register="estimate",
    )
    assert msg.startswith("Estimate —")
    assert "Connected" in msg


def test_insufficient_info_house_phrase():
    assert format_operator_message("insufficient_info") == HOUSE_PHRASING["insufficient_info"]


def test_format_outcome_digest_shapes_real_outcomes():
    text = format_outcome_digest(
        [
            {
                "status": "failed",
                "summary": "Write blocked: this canvas step needs an approved run.",
                "source": "api",
                "run_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            },
            {
                "status": "completed",
                "summary": "List created in Apollo",
                "source": "api",
                "verified": True,
            },
        ],
        title="Executive Digest",
        period_label="Last 24 hours",
        allow_humor=False,
    )
    assert "Executive Digest" in text
    assert "1 completed · 1 failed" in text
    assert "Write blocked" in text
    assert "Verified: List created" in text
    assert "Done — clean run" not in text  # humor off when failures present


def test_format_outcome_digest_clean_window_may_use_light_touch():
    text = format_outcome_digest(
        [{"status": "completed", "summary": "Sync finished", "verified": True}],
        allow_humor=True,
    )
    assert "Done — clean run" in text
