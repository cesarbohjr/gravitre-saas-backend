"""2.0-F WRITE compile — ActionSpec + ledger, HMAC invoke, approval stays."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.connectors.action_catalog.f1_write_slice import F1_WRITE_CATALOG_ACTIONS, is_f1_write_action
from app.connectors.action_catalog.registry import get_action_spec
from app.services.react_write_gate import WRITE_APPROVAL_REQUIRED, block_react_write_execution
from app.services.tool_registry import get_tool_registry
from app.services.tool_service import invoke_tool
from app.services.tool_types import ToolContext, ToolValidationError
from app.services.write_preflight import compile_write_for_context, preflight_write_action


def _ctx(**overrides) -> ToolContext:
    base = dict(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )
    base.update(overrides)
    return ToolContext(**base)


def test_write_specs_materialize_with_source_rules_and_risk_class() -> None:
    for key in F1_WRITE_CATALOG_ACTIONS:
        spec = get_action_spec(key)
        assert spec is not None, key
        assert spec.kind == "write"
        assert spec.governance_classification == "write"
        assert spec.risk_class in {"external_send", "crm_create", "browser_interact"}
        assert spec.parameter_source_rules
        assert spec.spec_revision
        assert is_f1_write_action(key)


def test_email_send_compiles_from_user_message_and_ledger() -> None:
    result = preflight_write_action(
        context={
            "action_key": "email.send",
            "org_id": "org-1",
            "user_message": "Send an email to ada@example.com subject line, Q3 update and body of the email say: Pipeline is up.",
            "proposed_args": {"to": "model-invented@example.com", "subject": "wrong"},
            "connected_integrations": ["email"],
        }
    )
    assert result.ok, result.as_dict()
    assert result.compiled_parameters["to"] == "ada@example.com"
    assert result.compiled_parameters["subject"] == "Q3 update"
    assert "Pipeline is up" in str(result.compiled_parameters["body"])
    assert result.proof_digest


def test_email_send_missing_recipient_asks_user_not_auto_fill() -> None:
    result = preflight_write_action(
        context={
            "action_key": "email.send",
            "org_id": "org-1",
            "user_message": "Send the proposal.",
            "proposed_args": {},
            "connected_integrations": ["email"],
        }
    )
    assert not result.ok
    assert result.error_class == "GENUINE_USER_CLARIFICATION_REQUIRED"
    assert result.provider_invoked is False


def test_slack_post_compiles_channel_from_message() -> None:
    result = preflight_write_action(
        context={
            "action_key": "slack.post_message",
            "org_id": "org-1",
            "user_message": 'Post "standup notes" to #sales',
            "proposed_args": {},
            "connected_integrations": ["slack"],
        }
    )
    assert result.ok, result.as_dict()
    assert result.compiled_parameters["channel"] == "sales"
    assert "standup notes" in str(result.compiled_parameters.get("text") or "")


def test_invoke_write_without_hmac_does_not_call_provider() -> None:
    ctx = _ctx()
    with patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None):
        with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
            mock_exec.return_value = lambda *_a, **_k: None
            with pytest.raises(ToolValidationError) as exc:
                invoke_tool(ctx, "email.send", {"to": "ada@example.com", "subject": "Hi", "body": "Hello"})
            assert exc.value.code == "PREFLIGHT_REQUIRED"
            mock_exec.assert_not_called()


def test_f1_write_cannot_auto_run_without_approval() -> None:
    blocked = block_react_write_execution(
        "email_send",
        {"to": "ada@example.com", "subject": "Hi", "body": "Hello"},
        registry=get_tool_registry(),
        client=MagicMock(),
        org_id="org-1",
        user_id="user-1",
        user_message='Email ada@example.com subject line, Hi and body of the email say: Hello',
        connected_integrations=["email"],
    )
    assert blocked is not None
    assert blocked["pending_approval"] is True
    assert blocked["error_code"] == WRITE_APPROVAL_REQUIRED
    assert blocked["args"]["to"] == "ada@example.com"


def test_read_preflight_still_rejects_writes() -> None:
    from app.services.read_preflight import preflight_read_action

    result = preflight_read_action(context={"action_key": "email.send", "org_id": "org-1"})
    assert not result.ok
    assert result.error_class in {"ACTION_UNAVAILABLE", "PERMISSION_BLOCKED"}


def test_compile_write_for_context_hmac_roundtrip() -> None:
    ctx = _ctx()
    proof = compile_write_for_context(
        ctx=ctx,
        invoke_action="email.send",
        args={"to": "other@example.com"},
        user_message="Send ada@example.com subject line, Hello and body of the email say: Confirmed.",
        connected_integrations=["email"],
    )
    assert proof.ok
    bound = replace(ctx, preflight_result=proof)
    with patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None):
        with patch("app.services.tool_service.enforce_rate_limit"):
            with patch("app.services.tool_service.write_audit_event"):
                with patch(
                    "app.services.agent_tool_permissions.list_agent_tool_permissions",
                    return_value=[{"connector_type": "email", "scopes": ["email:send"], "expires_at": None}],
                ):
                    with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
                        mock_exec.return_value = lambda *_a, **_k: None
                        invoke_tool(bound, "email.send", dict(proof.compiled_parameters))
                        mock_exec.assert_called()


def test_invoke_write_hmac_runs_before_capability_without_patch() -> None:
    ctx = _ctx()
    with patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
        mock_exec.return_value = lambda *_a, **_k: None
        with pytest.raises(ToolValidationError) as exc:
            invoke_tool(ctx, "email.send", {"to": "ada@example.com", "subject": "Hi", "body": "Hello"})
        assert exc.value.code == "PREFLIGHT_REQUIRED"
        mock_exec.assert_not_called()


def test_hubspot_contact_compiles_email_from_message() -> None:
    result = preflight_write_action(
        context={
            "action_key": "hubspot.contacts.create",
            "org_id": "org-1",
            "user_message": "Create a HubSpot contact for ada@example.com named Ada Lovelace",
            "proposed_args": {},
            "connected_integrations": ["hubspot"],
        }
    )
    assert result.ok, result.as_dict()
    assert result.compiled_parameters["email"] == "ada@example.com"


def test_email_approval_ux_surfaces_to_subject_body() -> None:
    from app.services.chat_connector_models import ConnectorActionPlan
    from app.services.connector_action_workflows import format_write_approval_message

    plan = ConnectorActionPlan(
        tool_name="email_send",
        invoke_action="email.send",
        integration="email",
        kind="write",
        label="Send email",
        args={"to": "ada@example.com", "subject": "Q3 update", "body": "Pipeline is up."},
    )
    message = format_write_approval_message(plan)
    assert "ada@example.com" in message
    assert "Q3 update" in message
    assert "Pipeline is up." in message
    assert "yes" in message.lower()


def test_slack_approval_ux_surfaces_channel_and_text() -> None:
    from app.services.chat_connector_models import ConnectorActionPlan
    from app.services.connector_action_workflows import format_write_approval_message

    plan = ConnectorActionPlan(
        tool_name="slack_post_message",
        invoke_action="slack.post_message",
        integration="slack",
        kind="write",
        label="Post Slack message",
        args={"channel": "sales", "text": "standup notes"},
    )
    message = format_write_approval_message(plan)
    assert "sales" in message
    assert "standup notes" in message


def test_catalog_authority_always_approves_f1_writes() -> None:
    from app.services.catalog_write_authority import invoke_action_requires_write_approval

    for key in F1_WRITE_CATALOG_ACTIONS:
        assert invoke_action_requires_write_approval(key) is True


def test_canvas_f1_write_compile_attaches_hmac_proof() -> None:
    from app.services.canvas_write_gate import bind_f1_write_hmac_context

    ctx = _ctx()
    bound_ctx, params = bind_f1_write_hmac_context(
        tool_ctx=ctx,
        action="email.send",
        params={"to": "model@example.com"},
        intent_text="Send ada@example.com subject line, Hello and body of the email say: Confirmed.",
    )
    assert bound_ctx.preflight_result is not None
    assert bound_ctx.preflight_result.ok
    assert params["to"] == "ada@example.com"
    assert params["subject"] == "Hello"


def test_react_gate_replaces_model_invented_recipient() -> None:
    blocked = block_react_write_execution(
        "email_send",
        {"to": "model-invented@example.com", "subject": "wrong", "body": "wrong"},
        registry=get_tool_registry(),
        client=MagicMock(),
        org_id="org-1",
        user_id="user-1",
        user_message="Email ada@example.com subject line, Hi and body of the email say: Hello",
        connected_integrations=["email"],
    )
    assert blocked is not None
    assert blocked["pending_approval"] is True
    assert blocked["args"]["to"] == "ada@example.com"
