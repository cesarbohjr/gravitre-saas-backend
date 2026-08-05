"""Browser extension bridge — allowlist, surfaces, durable write confirm gate."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.extension_bridge_service import (
    EXTENSION_ALLOWED_ACTIONS,
    EXTENSION_CHAT_SIDE_PANEL_STEP_THRESHOLD,
    _apollo_person_id,
    _hubspot_contact_id,
    assert_extension_action,
    answer_from_extension_page_context,
    build_extension_chat_system_prompt,
    chat_from_extension,
    detect_surface,
    execute_extension_action,
    format_extension_page_context_block,
    should_handoff_extension_chat,
)


def test_detect_surface_linkedin_gmail_outlook_company():
    assert detect_surface("https://www.linkedin.com/in/jane-doe") == "linkedin"
    assert detect_surface("https://mail.google.com/mail/u/0/#inbox") == "gmail"
    assert detect_surface("https://outlook.office.com/mail/") == "outlook"
    assert detect_surface("https://acme.example/pricing") == "company_site"
    assert detect_surface("https://acme.example/careers") == "careers_about"
    assert detect_surface("https://acme.my.salesforce.com/lightning/r/Lead/00Q/view") == "salesforce"
    assert detect_surface("https://app.slack.com/client/T123/C456") == "slack"


def test_extension_chat_page_context_fenced_and_handoff_heuristics():
    block = format_extension_page_context_block(
        page_url="https://www.linkedin.com/in/jane-doe",
        page_context={"fullName": "Jane Doe", "company": "Acme", "title": "CTO"},
    )
    assert "Jane Doe" in block
    assert "Acme" in block
    assert "DATA only" in block
    prompt = build_extension_chat_system_prompt(
        base_prompt="You are Gravitre AI.",
        page_url="https://www.linkedin.com/in/jane-doe",
        page_context={"fullName": "Jane Doe"},
    )
    assert "<page_context>" in prompt
    assert "Jane Doe" in prompt
    assert "browser overlay" in prompt.lower()
    quick, reason = should_handoff_extension_chat(
        message="Who is this person?",
        answer="Jane Doe appears to be a CTO at Acme.",
    )
    assert quick is False
    assert reason == "quick_answer"
    handoff, hreason = should_handoff_extension_chat(
        message="Create a HubSpot list for them",
        answer="I can help with that in full chat.",
    )
    assert handoff is True
    assert hreason == "action_or_write_intent"
    multi, mreason = should_handoff_extension_chat(
        message="What should we do next?",
        answer="Here is a plan.",
        pending_task={
            "params": {
                "steps": [
                    {"label": "Step A"},
                    {"label": "Step B"},
                    {"label": "Step C"},
                ]
            }
        },
    )
    assert EXTENSION_CHAT_SIDE_PANEL_STEP_THRESHOLD == 3
    assert multi is True
    assert mreason == "multi_step_progress"
    page_answer = answer_from_extension_page_context(
        message="what is this person's full name, title, and company?",
        page_context={
            "fullName": "Casey Operator",
            "title": "Head of Revenue Ops",
            "company": "Gravitree Smoke Co",
        },
    )
    assert page_answer is not None
    assert "Casey Operator" in page_answer
    assert "Gravitree Smoke Co" in page_answer


def test_assert_extension_action_blocks_unknown():
    with pytest.raises(ValueError, match="not allowed"):
        assert_extension_action("linkedin.messages.send")


@pytest.mark.asyncio
async def test_extension_chat_write_intent_runs_execute_task_streaming():
    """Write intents must not short-circuit before LIVE progressive / write authority."""
    from app.operators.stream_events import AssistantStreamComplete

    async def _stream(**_kwargs):
        yield AssistantStreamComplete(
            full_content="Reply **yes** to create the Apollo list.",
            tool_results=[],
            react_result=None,
            model="test",
            pending_task={"status": "awaiting_confirm", "params": {"steps": [{"label": "create"}]}},
            message_id="msg-1",
        )

    settings = MagicMock()
    conv_svc = MagicMock()
    conv_svc.ensure_owned_conversation = AsyncMock(return_value="conv-write-1")
    intel = MagicMock()
    intel.execute_task_streaming = _stream

    with (
        patch("app.config.get_settings", return_value=settings),
        patch(
            "app.services.conversation_state_service.get_conversation_state_service",
            return_value=conv_svc,
        ),
        patch("app.operators.agent_intelligence.get_agent_intelligence", return_value=intel),
        patch("app.routers.assistant._persist_conversation_turn"),
        patch("app.workflows.audit.write_audit_event"),
        patch("app.workflows.repository.get_supabase_client", return_value=MagicMock()),
    ):
        out = await chat_from_extension(
            settings=settings,
            org_id="org-1",
            user_id="user-1",
            message="Create an Apollo contact list named a5d-gate",
            page_context={"url": "https://example.com", "title": "probe"},
            conversation_id="conv-write-1",
        )

    assert out["path"] == "execute_task_streaming"
    assert out["path"] != "handoff_short_circuit"
    assert out["needsHandoff"] is True
    assert "yes" in (out.get("answer") or "").lower()
    assert out["conversationId"] == "conv-write-1"


def test_v1_allowlist_includes_apollo_hubspot_core():
    assert "apollo.people.match" in EXTENSION_ALLOWED_ACTIONS
    assert "apollo.lists.add" in EXTENSION_ALLOWED_ACTIONS
    assert "hubspot.contacts.create" in EXTENSION_ALLOWED_ACTIONS
    assert "hubspot.lists.add_contact" in EXTENSION_ALLOWED_ACTIONS


def test_extract_apollo_and_hubspot_ids():
    assert _apollo_person_id({"person": {"id": "ap123"}}) == "ap123"
    assert _apollo_person_id({"primary_contact_id": "c9"}) == "c9"
    assert _hubspot_contact_id({"results": [{"id": "15"}]}) == "15"
    assert _hubspot_contact_id({"contact_id": "99"}) == "99"


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.client = MagicMock()
    ctx.org_id = "org-1"
    ctx.actor_id = "user-1"
    ctx.environment_name = "production"
    return ctx


@patch("app.services.extension_bridge_service.assert_extension_action", side_effect=lambda a: a)
@patch("app.services.extension_bridge_service.invoke_action_requires_write_approval", return_value=True)
@patch("app.services.approval_record_service.create_contract_approval")
def test_write_propose_stages_awaiting_confirm_never_invokes(mock_create, _auth, _assert):
    mock_create.return_value = {"id": "appr-1"}
    ctx = _ctx()
    out = execute_extension_action(
        ctx,
        org_id="org-1",
        user_id="user-1",
        action="hubspot.contacts.create",
        params={"properties": {"email": "a@b.com"}},
        page_url="https://www.linkedin.com/in/jane",
        confirmation_token=None,
    )
    assert out["status"] == "needs_confirmation"
    assert out["confirmationToken"]
    assert out["approvalId"] == "appr-1"
    mock_create.assert_called_once()
    context = mock_create.call_args.kwargs["context"]
    assert context["status"] == "awaiting_confirm"
    assert context["invoke_action"] == "hubspot.contacts.create"


@patch("app.services.extension_bridge_service.assert_extension_action", side_effect=lambda a: a)
@patch("app.services.extension_bridge_service._run_confirmed_extension_action")
def test_client_confirmed_flag_cannot_skip_token(mock_run, _assert):
    """No confirmationToken ⇒ write is staged; invoke_tool path never reached."""
    with patch(
        "app.services.extension_bridge_service._stage_extension_write_confirmation",
        return_value={"status": "needs_confirmation", "confirmationToken": "tok"},
    ) as stage:
        out = execute_extension_action(
            _ctx(),
            org_id="org-1",
            user_id="user-1",
            action="apollo.lists.add",
            params={"entity_ids": ["1"]},
            page_url=None,
            confirmation_token=None,
        )
    assert out["status"] == "needs_confirmation"
    stage.assert_called_once()
    mock_run.assert_not_called()


@patch("app.services.extension_bridge_service.assert_extension_action", side_effect=lambda a: a)
@patch("app.services.extension_bridge_service._run_confirmed_extension_action")
@patch("app.services.extension_bridge_service._consume_extension_pending_confirm")
@patch("app.services.extension_bridge_service._load_extension_pending_confirm")
def test_confirm_turn_uses_server_staged_args(mock_load, mock_consume, mock_run, _assert):
    mock_load.return_value = (
        {"id": "appr-9", "context": {"confirmation_token": "tok", "status": "awaiting_confirm"}},
        {
            "invoke_action": "hubspot.contacts.create",
            "args": {"properties": {"email": "staged@example.com"}},
            "page_url": "https://www.linkedin.com/in/jane",
            "approval_id": "appr-9",
        },
    )
    mock_run.return_value = {"status": "completed", "success": True}
    # Client-supplied params must be ignored on confirm turn.
    execute_extension_action(
        _ctx(),
        org_id="org-1",
        user_id="user-1",
        action="hubspot.contacts.create",
        params={"properties": {"email": "attacker@evil.com"}},
        page_url=None,
        confirmation_token="tok",
    )
    mock_consume.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["params"]["properties"]["email"] == "staged@example.com"
    assert kwargs["approval_id"] == "appr-9"


def test_confirm_without_token_row_raises():
    ctx = _ctx()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.contains.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    ctx.client.table.return_value = chain
    with pytest.raises(ValueError, match="awaiting_confirm|not valid for browser extension"):
        execute_extension_action(
            ctx,
            org_id="org-1",
            user_id="user-1",
            action=None,
            params={},
            page_url=None,
            confirmation_token="forged-token",
        )
