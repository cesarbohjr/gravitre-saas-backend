from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.tool_service import invoke_tool, list_registered_actions
from app.services.tool_types import (
    NormalizedResult,
    ToolContext,
    ToolNotFoundError,
    ToolRateLimitedError,
    ToolValidationError,
)


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(
        disable_connectors=False,
        connector_secrets_encryption_key="k" * 32,
        private_connector_runtime_enabled=True,
    )
    client = MagicMock()
    return ToolContext(
        settings=settings,
        client=client,
        org_id="org-1",
        actor_id="user-1",
        run_id="run-1",
        step_id="step-1",
        step_type="slack_post_message",
    )


def test_list_registered_actions():
    actions = list_registered_actions()
    assert "slack.post_message" in actions
    assert "email.send" in actions
    assert "webhook.post" in actions


def test_invoke_unknown_action(tool_ctx: ToolContext):
    with pytest.raises(ToolNotFoundError):
        invoke_tool(tool_ctx, "hubspot.contacts.archive", {})


def test_invoke_slack_success(tool_ctx: ToolContext):
    conn = {"id": "conn-slack", "type": "slack", "status": "active"}
    with patch("app.services.tool_service.get_connector_by_type", return_value=conn):
        with patch("app.services.tool_service.get_decrypted_secret", return_value="xoxb-test"):
            with patch("app.services.tool_service.enforce_rate_limit"):
                with patch("app.services.tool_service.send_slack_message", return_value={"ts": "123", "_latency_ms": 42}):
                    with patch("app.services.tool_service.write_audit_event"):
                        result = invoke_tool(
                            tool_ctx,
                            "slack.post_message",
                            {"channel": "#general", "message": "hello"},
                        )
    assert result.success is True
    assert result.data["ok"] is True
    assert result.connector_id == "conn-slack"


def test_invoke_validation_error_no_retry(tool_ctx: ToolContext):
    with patch("app.services.tool_service._exec_slack_post_message", side_effect=ToolValidationError("bad channel")):
        with patch("app.services.tool_service.write_audit_event"):
            with patch("app.services.tool_service.time.sleep") as sleep_mock:
                result = invoke_tool(tool_ctx, "slack.post_message", {"channel": "", "message": "x"})
    assert result.success is False
    assert result.error_code == "validation_error"
    sleep_mock.assert_not_called()


def test_invoke_rate_limit_retries(tool_ctx: ToolContext):
    calls = {"n": 0}

    def flaky(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ToolRateLimitedError("slow down")
        return NormalizedResult(
            success=True,
            action="slack.post_message",
            data={"ok": True},
            connector_id="c1",
        )

    with patch("app.services.tool_service._TOOL_REGISTRY", {"slack.post_message": flaky}):
        with patch("app.services.tool_service.write_audit_event"):
            with patch("app.services.tool_service.time.sleep"):
                result = invoke_tool(tool_ctx, "slack.post_message", {})
    assert result.success is True
    assert calls["n"] == 2
