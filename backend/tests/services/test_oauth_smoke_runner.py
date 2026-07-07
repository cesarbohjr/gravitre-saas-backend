"""Unit tests for oauth_smoke_runner classification and ToolResult conversion."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.oauth_smoke_runner import (
    SmokeActionPlan,
    SmokeBuildContext,
    classify_failure,
    normalized_to_tool_result,
    run_smoke_action,
    smoke_action_plans,
    validate_tool_result_payload,
    _build_params,
)
from app.services.tool_types import NormalizedResult, ToolContext


def test_classify_auth_failure():
    status, fix = classify_failure(error_code="auth_expired", error_message="401 Unauthorized")
    assert status == "auth_failure"
    assert "Reconnect" in fix


def test_classify_missing_scopes():
    status, _fix = classify_failure(
        error_code="auth_expired",
        error_message="403 insufficient scope for hubspot.contacts.read",
    )
    assert status == "missing_scopes"


def test_classify_invalid_schema():
    status, _fix = classify_failure(
        error_code="validation_error",
        error_message="hubspot.contacts.search requires filter_groups array",
    )
    assert status == "invalid_schema"


def test_classify_api_error():
    status, _fix = classify_failure(error_message="Upstream 502 Bad Gateway", http_status=502)
    assert status == "api_error"


def test_normalized_to_tool_result_success():
    result = NormalizedResult(
        success=True,
        action="slack.conversations.list",
        connector_id="c1",
        data={"channels": []},
    )
    payload = normalized_to_tool_result("slack_conversations_list", result)
    assert payload["success"] is True
    assert payload["result"] == {"channels": []}
    assert validate_tool_result_payload(payload, action_id="slack.conversations.list")


def test_normalized_to_tool_result_failure():
    result = NormalizedResult(
        success=False,
        action="hubspot.contacts.get",
        error_code="validation_error",
        error_message="missing contact_id",
    )
    payload = normalized_to_tool_result("hubspot_contacts_get", result)
    assert payload["success"] is False
    assert payload["error_code"] == "validation_error"
    assert validate_tool_result_payload(payload, action_id="hubspot.contacts.get")


def test_smoke_plans_skip_destructive_by_default():
    plans = smoke_action_plans(include_writes=True, allow_destructive=False)
    assert all(not p.destructive for p in plans)


def test_run_smoke_action_skips_unregistered(monkeypatch):
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=SimpleNamespace(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )
    plan = SmokeActionPlan("hubspot", "hubspot", "hubspot.not.real", "read")
    monkeypatch.setattr(
        "app.services.oauth_smoke_runner.list_registered_actions",
        lambda: ["hubspot.contacts.search"],
    )
    row = run_smoke_action(
        ctx,
        plan,
        run_id="run-1",
        env={},
        enable_writes=False,
        allow_destructive=False,
        validate_remote_auth=False,
    )
    assert row.status == "skipped"


def test_run_smoke_action_write_requires_sandbox(monkeypatch):
    ctx = ToolContext(
        settings=SimpleNamespace(disable_connectors=False, connector_secrets_encryption_key="k" * 32),
        client=SimpleNamespace(),
        org_id="org-1",
        actor_id="user-1",
        environment_name="production",
    )
    plan = SmokeActionPlan(
        "hubspot",
        "hubspot",
        "hubspot.contacts.create",
        "write",
        static_params={"properties": {"email": "x@example.com"}},
        skip_unless_sandbox=True,
    )
    monkeypatch.setattr(
        "app.services.oauth_smoke_runner.list_registered_actions",
        lambda: ["hubspot.contacts.create"],
    )
    monkeypatch.setattr(
        "app.services.oauth_smoke_runner._resolve_connector",
        lambda *_a, **_k: {"id": "c1", "type": "hubspot", "config": {}},
    )
    row = run_smoke_action(
        ctx,
        plan,
        run_id="run-1",
        env={},
        enable_writes=True,
        allow_destructive=False,
        validate_remote_auth=False,
    )
    assert row.status == "skipped"
    assert "sandbox" in (row.detail or "").lower()


def test_param_builder_uses_run_id():
    ts_plan = SmokeActionPlan(
        "hubspot",
        "hubspot",
        "hubspot.contacts.create",
        "write",
        param_builder=lambda ctx: {"properties": {"email": f"{ctx.run_id}@example.com"}},
    )
    ctx = SmokeBuildContext(
        run_id="abc-123",
        org_id="org",
        environment_name="sandbox",
        connector={"id": "c1"},
        env={},
    )
    params = _build_params(ts_plan, ctx)
    assert params is not None
    assert "abc-123@example.com" in params["properties"]["email"]
