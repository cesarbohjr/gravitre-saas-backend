from unittest.mock import MagicMock

from app.connectors.google_oauth_tokens import (
    GoogleOAuthRefreshError,
    format_google_refresh_failure,
    token_request,
)
from app.services.execution_plan_adapters import project_pending_task_from_plan
from app.services.execution_plan_service import ExecutionPlan, ExecutionStep
from app.services.unified_turn_reasoning_service import _unified_stop_requested


def test_invalid_grant_is_reconnect_required() -> None:
    err = GoogleOAuthRefreshError("invalid_grant", "Token has been expired or revoked.")
    assert err.reconnect_required is True
    assert "Reconnect this Google connector" in format_google_refresh_failure(err)


def test_token_request_raises_typed_invalid_grant(monkeypatch) -> None:
    response = MagicMock()
    response.status_code = 400
    response.json.return_value = {
        "error": "invalid_grant",
        "error_description": "Token has been expired or revoked.",
    }

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return response

    monkeypatch.setattr("app.connectors.google_oauth_tokens.httpx.Client", lambda timeout=30.0: _Client())
    try:
        token_request(client_id="id", client_secret="secret", body={"grant_type": "refresh_token"})
        raise AssertionError("expected GoogleOAuthRefreshError")
    except GoogleOAuthRefreshError as exc:
        assert exc.reconnect_required is True


def test_project_pending_includes_plan_rationale_and_steps() -> None:
    plan = ExecutionPlan(
        plan_id="plan-1",
        summary="List HubSpot contacts",
        objective="Read reachable CRM",
        source="operator_act",
        steps=[
            ExecutionStep(
                step_id="s1",
                title="List contacts",
                kind="read",
                connector_id="hubspot",
                action_key="hubspot.contacts.list",
                meta={"rationale": "HubSpot is connected for this org."},
            )
        ],
    )
    pending = project_pending_task_from_plan(plan)
    assert pending["plan_summary"] == "List HubSpot contacts"
    assert pending["plan_rationale"] == "Read reachable CRM"
    assert pending["plan_steps"][0]["rationale"] == "HubSpot is connected for this org."
    assert pending["_projection_source"] == "execution_plan"


def test_unified_stop_requested_uses_chat_stop_flag(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.chat_turn_cancel_service.is_stop_requested",
        lambda org, conv, settings=None: org == "org-1" and conv == "conv-1",
    )
    assert _unified_stop_requested("org-1", "conv-1", None) is True
    assert _unified_stop_requested("org-1", "conv-2", None) is False
    assert _unified_stop_requested("org-1", None, None) is False
