"""Write authority on the invoke spine: every write declares why it may run."""
from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import write_authority as wa
from app.services.tool_types import ToolContext, ToolValidationError

SHADOW = SimpleNamespace(write_authority_mode="shadow")
ENFORCE = SimpleNamespace(write_authority_mode="enforce")
NORMAL_WRITE = "hubspot.contacts.update"
ALWAYS_APPROVE = "gmail.messages.send"
READ = "hubspot.contacts.get"


def test_reads_are_not_checked():
    assert wa.check_write_authority(READ, settings=ENFORCE) is None


def test_missing_authority_is_logged_in_shadow_and_allowed(caplog):
    with caplog.at_level(logging.WARNING):
        assert wa.check_write_authority(NORMAL_WRITE, settings=SHADOW, org_id="o1") is None
    assert "write_authority_violation" in caplog.text and "no_authority" in caplog.text


def test_missing_authority_is_refused_in_enforce():
    with pytest.raises(wa.WriteAuthorityError):
        wa.check_write_authority(NORMAL_WRITE, settings=ENFORCE)


@pytest.mark.parametrize("kind", ["human", "run", "compensation", "internal"])
def test_declared_authority_allows_any_write(kind):
    with wa.write_authority(kind, "ref-1"):
        got = wa.check_write_authority(ALWAYS_APPROVE, settings=ENFORCE)
    assert got == wa.WriteAuthority(kind, "ref-1")


def test_policy_allows_ordinary_write_but_never_an_always_approve_action():
    with wa.write_authority("policy", "react:a1"):
        assert wa.check_write_authority(NORMAL_WRITE, settings=ENFORCE).kind == "policy"
        with pytest.raises(wa.WriteAuthorityError):
            wa.check_write_authority(ALWAYS_APPROVE, settings=ENFORCE)
        with pytest.raises(wa.WriteAuthorityError):
            wa.check_write_authority("freshservice.tickets.update_status", settings=ENFORCE)


def test_default_mode_is_shadow():
    from app.config import Settings

    assert Settings.model_fields["write_authority_mode"].default == "shadow"
    assert wa._mode(SimpleNamespace()) == "shadow"
    assert wa._mode(SimpleNamespace(write_authority_mode="bogus")) == "shadow"


def test_authority_scope_resets_and_rejects_unknown_kind():
    with wa.write_authority("human"):
        assert wa.current_write_authority().kind == "human"
    assert wa.current_write_authority() is None
    with pytest.raises(ValueError):
        with wa.write_authority("trust-me"):
            pass


def test_decorator_sync_and_async():
    @wa.authorized("compensation", "undo")
    def sync_fn():
        return wa.current_write_authority()

    @wa.authorized("human")
    async def async_fn():
        return wa.current_write_authority()

    assert sync_fn() == wa.WriteAuthority("compensation", "undo")
    assert asyncio.run(async_fn()) == wa.WriteAuthority("human", "async_fn")
    assert wa.current_write_authority() is None


def test_invoke_tool_refuses_unauthorized_write_before_any_provider_call():
    from app.services import tool_service

    ctx = ToolContext(settings=ENFORCE, client=None, org_id="o1", actor_id="u1")
    with (
        patch.object(tool_service, "_resolve_tool_executor", create=True) as resolve,
        patch("app.services.capability_availability.is_capability_action", return_value=False),
        patch("app.capability_ontology.resolver.resolve_capability_invoke_action", return_value=None),
    ):
        with pytest.raises(ToolValidationError) as exc:
            tool_service.invoke_tool(ctx, NORMAL_WRITE, {"id": "1"})
    assert exc.value.code == "WRITE_AUTHORITY_REQUIRED"
    resolve.assert_not_called()


def test_canvas_step_invokes_under_run_authority():
    from app.workflows import handlers

    seen = []
    context = SimpleNamespace(run_id="run-9", config={}, parameters={})
    with (
        patch.object(handlers, "tool_context_from_step", return_value=MagicMock()),
        patch("app.services.canvas_write_gate.bind_f1_write_hmac_context", side_effect=lambda **k: (k["tool_ctx"], k["params"])),
        patch("app.services.sealed_read_execution.bind_read_preflight", side_effect=lambda c, a, b, **k: (c, b, None)),
        patch.object(handlers, "invoke_tool", side_effect=lambda *a: seen.append(wa.current_write_authority())),
    ):
        handlers._invoke_canvas_registered_tool(context, NORMAL_WRITE, {})
    assert seen == [wa.WriteAuthority("run", "run-9")]


def _chat_service():
    from app.services.chat_connector_execution_service import ChatConnectorExecutionService

    svc = ChatConnectorExecutionService.__new__(ChatConnectorExecutionService)
    seen = []

    async def fake(**_k):
        seen.append(wa.current_write_authority())
        return "done"

    svc._execute_plan_shielded = fake
    return svc, seen


def test_chat_confirmed_write_is_human_and_unconfirmed_is_policy():
    svc, seen = _chat_service()
    asyncio.run(svc.execute_plan(conversation_id="c1", approved_params={"x": 1}))
    asyncio.run(svc.execute_plan(conversation_id="c1"))
    assert seen == [wa.WriteAuthority("human", "chat:c1"), wa.WriteAuthority("policy", "chat:c1")]


def test_chat_keeps_outer_authority():
    svc, seen = _chat_service()

    async def go():
        with wa.write_authority("human", "approval:r1"):
            await svc.execute_plan(conversation_id="c1")

    asyncio.run(go())
    assert seen == [wa.WriteAuthority("human", "approval:r1")]


def test_callers_without_a_gate_are_declared():
    from app.operators.agent_jobs import push_job_deliverable
    from app.services.compensation_service import execute_compensations, notify_compensation_webhook
    from app.services.extension_bridge_service import _run_confirmed_extension_action

    for fn in (push_job_deliverable, execute_compensations, notify_compensation_webhook, _run_confirmed_extension_action):
        assert hasattr(fn, "__wrapped__"), fn.__name__
