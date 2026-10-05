"""Internal callers compile + seal F1 READs before invoke_tool (no PREFLIGHT_REQUIRED)."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.connector_resource_resolver import ResourceResolution
from app.services.read_preflight import PreflightResult
from app.services.sealed_read_execution import bind_read_preflight, invoke_compiled_read
from app.services.tool_types import NormalizedResult, ToolContext, ToolValidationError


def _ctx(**overrides) -> ToolContext:
    base = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )
    return replace(base, **overrides)


def _portal() -> ResourceResolution:
    return ResourceResolution(
        status="resolved",
        connector_id="hubspot",
        connection_id="conn-1",
        resource_type="portal",
        resource_id="99887",
        display_name="99887",
        confidence=0.98,
        resolution_reason="linked_config",
        candidate_count=1,
    )


@contextmanager
def _provider():
    seen: dict = {}

    def _executor(ctx, params, *_a, **_k):
        seen["ctx"] = ctx
        seen["params"] = dict(params)
        return NormalizedResult(success=True, action="hubspot.contacts.search", data={"results": []})

    with patch("app.services.read_preflight.resolve_resource", return_value=_portal()), patch(
        "app.services.tool_service.enforce_rate_limit"
    ), patch("app.services.tool_service.write_audit_event"), patch(
        "app.services.agent_tool_permissions.list_agent_tool_permissions",
        return_value=[{"connector_type": "hubspot", "scopes": ["hubspot:read"], "expires_at": None}],
    ), patch("app.services.tool_service._resolve_tool_executor") as mock_exec:
        mock_exec.return_value = _executor
        yield mock_exec, seen


def test_direct_invoke_still_refuses_uncompiled_f1_read():
    from app.services.tool_service import invoke_tool

    with _provider() as (mock_exec, _seen), pytest.raises(ToolValidationError) as exc:
        invoke_tool(_ctx(), "hubspot.contacts.search", {"query": "ada@example.com"})
    assert exc.value.code == "PREFLIGHT_REQUIRED"
    mock_exec.assert_not_called()


def test_invoke_compiled_read_seals_and_executes_f1_read():
    with _provider() as (mock_exec, seen):
        out = invoke_compiled_read(_ctx(), "hubspot.contacts.search", {"query": "ada@example.com", "limit": 1})
    assert out.success is True
    mock_exec.assert_called()
    assert seen["params"]["query"] == "ada@example.com"
    assert seen["params"]["limit"] == 1


def test_invoke_compiled_read_strips_forged_markers():
    with _provider() as (_mock_exec, seen):
        out = invoke_compiled_read(_ctx(), "hubspot.contacts.search", {"query": "Ada", "_preflight_ok": "forged"})
    assert out.success is True
    assert "_preflight_ok" not in seen["params"]


def test_blocked_compile_returns_failure_without_calling_provider():
    with _provider() as (mock_exec, _seen):
        out = invoke_compiled_read(_ctx(), "hubspot.deals.search", {})
    assert out.success is False
    assert out.error_code == "WRONG_SIBLING_ACTION"
    mock_exec.assert_not_called()


def test_write_proof_on_ctx_is_replaced_for_read_back():
    write_proof = PreflightResult(status="ok", action_key="hubspot.contacts.create", proof_digest="x")
    with _provider() as (_mock_exec, _seen):
        bound_ctx, _params, blocked = bind_read_preflight(
            _ctx(preflight_result=write_proof), "hubspot.contacts.search", {"query": "Ada"}
        )
    assert blocked is None
    assert bound_ctx.preflight_result is not write_proof
    assert bound_ctx.preflight_result.action_key == "hubspot.contacts.search"
    assert bound_ctx.preflight_result.proof_digest


def test_non_f1_action_passes_through_untouched():
    ctx = _ctx()
    bound_ctx, params, blocked = bind_read_preflight(ctx, "apollo.lists.list", {"connector_id": "c1"})
    assert bound_ctx is ctx
    assert params == {"connector_id": "c1"}
    assert blocked is None


def test_workflow_step_compiles_f1_read(monkeypatch):
    from app.workflows import handlers

    calls: list = []

    def _fake_invoke(ctx, action, params):
        calls.append((ctx, action, params))
        return NormalizedResult(success=True, action=action)

    monkeypatch.setattr(handlers, "invoke_tool", _fake_invoke)
    monkeypatch.setattr(handlers, "tool_context_from_step", lambda _c: _ctx())
    with patch("app.services.read_preflight.resolve_resource", return_value=_portal()):
        handlers._invoke_canvas_registered_tool(MagicMock(), "hubspot.contacts.search", {"query": "Ada"})
    assert len(calls) == 1
    ctx, action, params = calls[0]
    assert action == "hubspot.contacts.search"
    assert isinstance(ctx.preflight_result, PreflightResult) and ctx.preflight_result.ok
    assert params["query"] == "Ada"
