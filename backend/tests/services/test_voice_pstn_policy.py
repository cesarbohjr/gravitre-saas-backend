"""Tests for PSTN voice policy differentiation (Finance vs Sales)."""
from __future__ import annotations

import pytest

from app.services.voice_pstn_policy import (
    infer_voice_policy_scope,
    resolve_voice_pstn_policy,
)


def test_infer_finance_collections_scope() -> None:
    assert infer_voice_policy_scope(department="finance", agent_name="Collections Bot") == "finance_collections"


def test_infer_sales_sdr_scope() -> None:
    assert infer_voice_policy_scope(department="sales", agent_name="SDR Outreach") == "sales_sdr"


def test_finance_blocks_calendar_booking_pattern() -> None:
    policy = resolve_voice_pstn_policy(
        None,
        org_id="org-1",
        agent_id=None,
        department="finance",
        agent_name="Collections",
    )
    assert "calendar.*.book" in policy.blocked_tool_patterns
    with pytest.raises(PermissionError):
        from app.services.voice_pstn_policy import enforce_pstn_tool_policy

        enforce_pstn_tool_policy(
            None,
            org_id="org-1",
            agent_id="agent-1",
            action_name="calendar.events.book",
            policy=policy,
            action_kind="write",
        )


def test_sales_allows_calendar_availability_read() -> None:
    policy = resolve_voice_pstn_policy(
        None,
        org_id="org-1",
        agent_id=None,
        department="sales",
        agent_name="SDR",
    )
    from app.services.voice_pstn_policy import enforce_pstn_tool_policy

    enforce_pstn_tool_policy(
        None,
        org_id="org-1",
        agent_id="agent-1",
        action_name="calendar.availability.read",
        policy=policy,
        action_kind="read",
    )
