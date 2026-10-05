"""Outcome Ownership: ambiguous writes are reconciled, never blindly replayed."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services import outcome_reconciliation as recon
from app.services.outcome_verification import is_write_action
from app.services.tool_service import invoke_tool, is_ambiguous_delivery_failure
from app.services.tool_types import (
    NormalizedResult,
    ToolContext,
    ToolOutcomeUncertainError,
)


@pytest.fixture
def tool_ctx() -> ToolContext:
    settings = SimpleNamespace(
        disable_connectors=False,
        connector_secrets_encryption_key="k" * 32,
        private_connector_runtime_enabled=True,
    )
    return ToolContext(
        settings=settings,
        client=MagicMock(),
        org_id="org-1",
        actor_id="user-1",
        run_id="run-1",
        step_id="step-1",
        step_type="slack_post_message",
    )


def _invoke_with(tool_ctx: ToolContext, action: str, impl):
    with patch("app.services.write_preflight.enforce_invoke_write_preflight", side_effect=lambda _c, _a, p: p), patch(
        "app.services.read_preflight.enforce_invoke_preflight", side_effect=lambda _c, _a, p: p
    ):
        with patch("app.services.tool_service._TOOL_REGISTRY", {action: impl}):
            with patch("app.services.tool_service.write_audit_event"):
                with patch("app.services.tool_service.time.sleep"):
                    return invoke_tool(tool_ctx, action, {})


def test_write_timeout_is_not_retried_and_reports_uncertain(tool_ctx: ToolContext) -> None:
    assert is_write_action("slack.post_message")
    calls = {"n": 0}

    def times_out(*_a, **_k):
        calls["n"] += 1
        raise httpx.ReadTimeout("read timed out")

    result = _invoke_with(tool_ctx, "slack.post_message", times_out)
    assert calls["n"] == 1, "a write that may have landed must not be replayed"
    assert result.success is False
    assert result.error_code == "outcome_uncertain"


def test_write_connect_error_is_safe_to_retry(tool_ctx: ToolContext) -> None:
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused")
        return NormalizedResult(success=True, action="slack.post_message", data={"ok": True, "ts": "1"})

    result = _invoke_with(tool_ctx, "slack.post_message", flaky)
    assert result.success is True
    assert calls["n"] == 2


def test_read_timeout_still_retries(tool_ctx: ToolContext) -> None:
    action = next(a for a in ("hubspot.contacts.search", "hubspot.contacts.get", "slack.channels.list") if not is_write_action(a))
    calls = {"n": 0}

    def flaky(*_a, **_k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("read timed out")
        return NormalizedResult(success=True, action=action, data={"results": []})

    result = _invoke_with(tool_ctx, action, flaky)
    assert result.success is True
    assert calls["n"] == 2


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (httpx.ReadTimeout("t"), True),
        (TimeoutError(), True),
        (httpx.ConnectError("connection refused"), False),
        (ToolOutcomeUncertainError("x"), True),
        (ValueError("bad input"), False),
    ],
)
def test_ambiguous_delivery_classification(exc: BaseException, expected: bool) -> None:
    assert is_ambiguous_delivery_failure(exc) is expected


def test_registry_maps_write_timeout_to_uncertain_payload() -> None:
    from app.services.tool_registry import _settle_write_payload

    payload = asyncio.run(
        _settle_write_payload(
            SimpleNamespace(client=None, org_id="o", settings=None),
            tool="hubspot_contacts_create",
            action="slack.post_message",
            params={},
            payload={"success": False, "error": "no response", "error_code": "connector_timeout"},
            verify=False,
        )
    )
    assert payload["error_code"] == "outcome_uncertain"
    assert payload["requires_reconciliation"] is True


def test_registry_attaches_receipt_evidence_to_successful_send() -> None:
    from app.services.tool_registry import _settle_write_payload

    payload = asyncio.run(
        _settle_write_payload(
            SimpleNamespace(client=None, org_id="o", settings=None),
            tool="slack_post_message",
            action="slack.post_message",
            params={"channel": "#g", "message": "hi"},
            payload={"success": True, "result": {"ok": True, "ts": "1700.1", "channel": "C1"}},
            verify=True,
        )
    )
    assert payload["outcome_verified"] is True
    assert payload["verification"]["method"] == "provider_receipt"


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def _lookup_ctx():
    return SimpleNamespace(connector_id="c1")


def test_reconcile_finds_created_record_by_natural_key(monkeypatch) -> None:
    monkeypatch.setattr(recon, "_registered", lambda a: a if a.endswith(".search") else None)
    monkeypatch.setattr(
        "app.services.sealed_read_execution.invoke_compiled_read",
        lambda ctx, action, params: SimpleNamespace(
            success=True, data={"results": [{"id": "42", "properties": {"email": "a@b.co"}}]}
        ),
    )
    out = recon.reconcile_uncertain_write(
        ctx=_lookup_ctx(),
        invoke_action="hubspot.contacts.create",
        args={"properties": {"email": "A@b.co"}},
    )
    assert out.state == "applied"
    assert out.resource_id == "42"
    assert out.evidence["method"] == "reconcile_lookup"


def test_reconcile_empty_filtered_search_proves_absence(monkeypatch) -> None:
    monkeypatch.setattr(recon, "_registered", lambda a: a if a.endswith(".search") else None)
    monkeypatch.setattr(
        "app.services.sealed_read_execution.invoke_compiled_read",
        lambda ctx, action, params: SimpleNamespace(success=True, data={"results": []}),
    )
    out = recon.reconcile_uncertain_write(
        ctx=_lookup_ctx(), invoke_action="hubspot.contacts.create", args={"email": "new@b.co"}
    )
    assert out.state == "not_applied"


def test_reconcile_unfiltered_page_without_record_is_not_proof(monkeypatch) -> None:
    monkeypatch.setattr(recon, "_registered", lambda a: a if a.endswith(".list") else None)
    monkeypatch.setattr(
        "app.services.sealed_read_execution.invoke_compiled_read",
        lambda ctx, action, params: SimpleNamespace(
            success=True, data={"results": [{"id": "1", "email": "someone@else.co"}]}
        ),
    )
    out = recon.reconcile_uncertain_write(
        ctx=_lookup_ctx(), invoke_action="hubspot.contacts.create", args={"email": "new@b.co"}
    )
    assert out.state == "unknown"


def test_reconcile_without_natural_key_is_unknown() -> None:
    out = recon.reconcile_uncertain_write(
        ctx=_lookup_ctx(), invoke_action="hubspot.notes.create", args={"body": "x"}
    )
    assert out.state == "unknown"
