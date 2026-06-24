"""Tests for notification_email_service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.services.notification_email_service import (
    build_swarm_completion_email,
    email_notifications_enabled,
    extract_next_steps,
    format_readable_text,
    resolve_user_email,
    send_swarm_completion_email,
)


def test_format_readable_text_strips_code_blocks():
    raw = "Summary here.\n```python\nprint('x')\n```\nMore text."
    assert "print" not in format_readable_text(raw)
    assert "Summary here." in format_readable_text(raw)


def test_extract_next_steps_deduplicates():
    subtasks = [
        {"result": {"recommendedAction": "Approve vendor", "recommended_actions": ["Approve vendor"]}},
    ]
    steps = extract_next_steps(subtasks, "Approve vendor")
    assert steps == ["Approve vendor"]


def test_resolve_user_email():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"email": "user@example.com"}]
    )
    assert resolve_user_email(client, "org-1", "user-1") == "user@example.com"


def test_email_notifications_enabled_defaults_true():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    assert email_notifications_enabled(client, "org-1", "user-1", "run_completed") is True


def test_email_notifications_enabled_respects_preference():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"preferences": {"email_run_completed": False}}]
    )
    assert email_notifications_enabled(client, "org-1", "user-1", "run_completed") is False


def test_build_swarm_completion_email_contains_summary_and_link():
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="secret",
        public_app_url="https://gravitre.app",
    )
    subject, html_body = build_swarm_completion_email(
        settings,
        swarm_run_id="swarm-1",
        objective="Pick a vendor",
        final_recommendation="Approve Acme Corp",
        final_confidence=0.92,
        decision_method="majority_vote",
        next_steps=["Schedule onboarding", "Notify legal"],
        dissenting_opinions=["Needs more pricing data"],
    )
    assert "Pick a vendor" in subject
    assert "Approve Acme Corp" in html_body
    assert "Suggested next steps" in html_body
    assert "https://gravitre.app/agents/swarm?runId=swarm-1" in html_body


@patch("app.services.notification_email_service.send_email_smtp")
def test_send_swarm_completion_email_uses_platform_smtp(mock_send):
    mock_send.return_value = (None, 12)
    settings = Settings(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        supabase_jwt_secret="secret",
        notification_smtp_host="smtp.example.com",
        notification_smtp_from="Gravitre <noreply@gravitre.app>",
    )
    client = MagicMock()
    users_table = MagicMock()
    users_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"email": "user@example.com"}]
    )
    prefs_table = MagicMock()
    prefs_table.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )

    def table(name: str):
        if name == "users":
            return users_table
        if name == "notification_preferences":
            return prefs_table
        return MagicMock()

    client.table.side_effect = table

    sent = send_swarm_completion_email(
        client,
        settings,
        org_id="org-1",
        user_id="user-1",
        swarm_run_id="swarm-1",
        objective="Evaluate vendor",
        final_recommendation="Approve vendor",
        final_confidence=0.88,
        decision_method="majority_vote",
        subtasks=[{"result": {"recommendedAction": "Approve vendor"}}],
    )
    assert sent is True
    mock_send.assert_called_once()
    assert mock_send.call_args.kwargs["to_addr"] == "user@example.com"
    assert mock_send.call_args.kwargs["content_type"] == "text/html"
