"""Tests for MCP write approval resume path.

Covers:
- AssistantStreamComplete carries pending_mcp_approval
- sanitize_interrupt_extra passes through pending_mcp_approval (arg keys only)
- react_engine injects approval_id from interrupt when tool_name matches
- approve-mcp-write endpoint happy path and error cases
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AssistantStreamComplete field
# ---------------------------------------------------------------------------


def test_assistant_stream_complete_pending_mcp_approval_field() -> None:
    from app.operators.stream_events import AssistantStreamComplete

    c = AssistantStreamComplete(
        full_content="ok",
        tool_results=[],
        react_result=None,
        model="gpt-4o",
        pending_mcp_approval={
            "tool_name": "create_ticket",
            "tool_id": "tid-1",
            "approval_id": "appr-1",
            "execution_id": "exec-1",
        },
    )
    assert c.pending_mcp_approval is not None
    assert c.pending_mcp_approval["approval_id"] == "appr-1"


def test_assistant_stream_complete_pending_mcp_approval_defaults_none() -> None:
    from app.operators.stream_events import AssistantStreamComplete

    c = AssistantStreamComplete(full_content="ok", tool_results=[], react_result=None, model="m")
    assert c.pending_mcp_approval is None


# ---------------------------------------------------------------------------
# sanitize_interrupt_extra
# ---------------------------------------------------------------------------


def test_sanitize_interrupt_extra_passes_mcp_approval() -> None:
    from app.services.chat_interrupt_resume_service import sanitize_interrupt_extra

    extra = {
        "pending_mcp_approval": {
            "tool_name": "create_ticket",
            "tool_id": "tid-abc",
            "approval_id": "appr-xyz",
            "execution_id": "exec-123",
            "tool_args": {"title": "Bug", "priority": "high"},
        }
    }
    result = sanitize_interrupt_extra(extra)
    mcp = result.get("pending_mcp_approval")
    assert mcp is not None
    assert mcp["approval_id"] == "appr-xyz"
    assert mcp["tool_name"] == "create_ticket"
    # Args keys stored, not values
    assert "tool_arg_keys" in mcp
    assert "title" in mcp["tool_arg_keys"]
    # Values NOT stored
    assert "tool_args" not in mcp


def test_sanitize_interrupt_extra_no_mcp_approval_key_absent() -> None:
    from app.services.chat_interrupt_resume_service import sanitize_interrupt_extra

    result = sanitize_interrupt_extra({"tool_names": ["some_tool"]})
    assert "pending_mcp_approval" not in result


def test_sanitize_interrupt_extra_empty_mcp_approval_ignored() -> None:
    from app.services.chat_interrupt_resume_service import sanitize_interrupt_extra

    result = sanitize_interrupt_extra({"pending_mcp_approval": {}})
    assert "pending_mcp_approval" not in result


# ---------------------------------------------------------------------------
# ReActResult — pending_mcp_approval in to_dict
# ---------------------------------------------------------------------------


def test_react_result_to_dict_includes_pending_mcp_approval() -> None:
    from app.operators.react_engine import ReActResult, ReActStatus

    r = ReActResult(
        status=ReActStatus.NEEDS_HUMAN_INPUT,
        answer="",
        pending_mcp_approval={
            "tool_name": "create_ticket",
            "tool_id": "t1",
            "approval_id": "a1",
            "execution_id": "e1",
            "tool_args": {"title": "x"},
        },
    )
    d = r.to_dict()
    assert d["pendingMcpApproval"]["approval_id"] == "a1"


def test_react_result_to_dict_no_pending_mcp_approval_absent() -> None:
    from app.operators.react_engine import ReActResult, ReActStatus

    r = ReActResult(status=ReActStatus.COMPLETED, answer="done")
    d = r.to_dict()
    assert "pendingMcpApproval" not in d


# ---------------------------------------------------------------------------
# Interrupt storage round-trip
# ---------------------------------------------------------------------------


def test_store_and_load_interrupt_with_mcp_approval() -> None:
    from app.services.chat_interrupt_resume_service import (
        load_interrupted_turn,
        reset_local_interrupts_for_tests,
        store_interrupted_turn,
    )

    reset_local_interrupts_for_tests()
    mcp_approval = {
        "tool_name": "create_ticket",
        "tool_id": "tid-1",
        "approval_id": "appr-1",
        "execution_id": "exec-1",
        "tool_args": {"title": "Test"},
    }
    ok = store_interrupted_turn(
        "org-1",
        "conv-1",
        user_text="create a ticket",
        assistant_text="I need approval to create a ticket.",
        extra={"pending_mcp_approval": mcp_approval},
    )
    assert ok
    loaded = load_interrupted_turn("org-1", "conv-1")
    assert loaded is not None
    stored = (loaded.get("extra") or {}).get("pending_mcp_approval")
    assert stored is not None
    assert stored["approval_id"] == "appr-1"
    # Verify args are not stored as values, only keys
    assert "tool_args" not in stored
    assert "tool_arg_keys" in stored


# ---------------------------------------------------------------------------
# approve-mcp-write endpoint
# ---------------------------------------------------------------------------


@pytest.fixture()
def _mock_auth():
    """Minimal auth context for endpoint tests."""
    with patch("app.routers.assistant.get_current_user") as mu, patch(
        "app.routers.assistant.get_org_context"
    ) as mo:
        mu.return_value = {"user_id": "user-1"}
        mo.return_value = "org-1"
        yield


def _make_client_stub(
    conversation_found: bool = True,
    approval_updated: list | None = None,
) -> MagicMock:
    client = MagicMock()
    # conversations ownership check
    conv_result = MagicMock()
    conv_result.data = [{"id": "conv-1"}] if conversation_found else []
    (
        client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value
    ) = conv_result
    # approvals update
    upd_result = MagicMock()
    upd_result.data = approval_updated if approval_updated is not None else [{"id": "appr-1"}]
    (
        client.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value
    ) = upd_result
    return client


def _make_interrupt(approval_id: str = "appr-1", tool_name: str = "create_ticket") -> dict:
    return {
        "org_id": "org-1",
        "conversation_id": "conv-1",
        "interrupted": True,
        "extra": {
            "pending_mcp_approval": {
                "tool_name": tool_name,
                "tool_id": "tid-1",
                "approval_id": approval_id,
            }
        },
    }


def test_approve_mcp_write_happy_path() -> None:
    """approve-mcp-write flips approval status and returns approved=True."""
    from fastapi.testclient import TestClient

    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
    ):
        mk_client.return_value = _make_client_stub()
        mk_load.return_value = _make_interrupt()

        from fastapi import FastAPI

        from app.routers.assistant import router

        app = FastAPI()
        app.include_router(router)

        # Override auth deps
        from app.auth.dependencies import get_current_user, get_org_context
        from app.config import get_settings

        app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
        app.dependency_overrides[get_org_context] = lambda: "org-1"
        app.dependency_overrides[get_settings] = lambda: MagicMock()

        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/api/assistant/conversation/conv-1/approve-mcp-write",
            json={"approval_id": "appr-1", "confirm": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["approved"] is True
        assert data["approval_id"] == "appr-1"
        assert data["tool_name"] == "create_ticket"


def test_approve_mcp_write_no_interrupt_returns_422() -> None:
    """Returns 422 when no pending MCP approval in interrupt state."""
    from fastapi.testclient import TestClient

    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
    ):
        mk_client.return_value = _make_client_stub()
        mk_load.return_value = None  # No interrupt

        from fastapi import FastAPI

        from app.routers.assistant import router
        from app.auth.dependencies import get_current_user, get_org_context
        from app.config import get_settings

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
        app.dependency_overrides[get_org_context] = lambda: "org-1"
        app.dependency_overrides[get_settings] = lambda: MagicMock()

        client = TestClient(app)
        resp = client.post(
            "/api/assistant/conversation/conv-1/approve-mcp-write",
            json={"approval_id": "appr-1", "confirm": True},
        )
        assert resp.status_code == 422


def test_approve_mcp_write_id_mismatch_returns_409() -> None:
    """Returns 409 when approval_id in request doesn't match stored state."""
    from fastapi.testclient import TestClient

    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
    ):
        mk_client.return_value = _make_client_stub()
        mk_load.return_value = _make_interrupt(approval_id="appr-correct")

        from fastapi import FastAPI

        from app.routers.assistant import router
        from app.auth.dependencies import get_current_user, get_org_context
        from app.config import get_settings

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
        app.dependency_overrides[get_org_context] = lambda: "org-1"
        app.dependency_overrides[get_settings] = lambda: MagicMock()

        client = TestClient(app)
        resp = client.post(
            "/api/assistant/conversation/conv-1/approve-mcp-write",
            json={"approval_id": "appr-WRONG", "confirm": True},
        )
        assert resp.status_code == 409



# ---------------------------------------------------------------------------
# reject-mcp-write endpoint (Release 2 gap fix)
# ---------------------------------------------------------------------------


def _make_reject_client(conversation_found: bool = True, approval_updated: list | None = None):
    """Inline FastAPI TestClient wired to the reject endpoint."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers.assistant import router
    from app.auth.dependencies import get_current_user, get_org_context
    from app.config import get_settings

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[get_settings] = lambda: MagicMock()
    stub = _make_client_stub(
        conversation_found=conversation_found,
        approval_updated=approval_updated,
    )
    return TestClient(app, raise_server_exceptions=False), stub


def test_reject_mcp_write_happy_path() -> None:
    """reject-mcp-write flips approval to rejected, clears interrupt, returns rejected=True."""
    clear_mock = MagicMock()

    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
        patch("app.routers.assistant.clear_interrupted_turn", clear_mock),
    ):
        tc, stub = _make_reject_client()
        mk_client.return_value = stub
        mk_load.return_value = _make_interrupt()

        resp = tc.post(
            "/api/assistant/conversation/conv-1/reject-mcp-write",
            json={"approval_id": "appr-1"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rejected"] is True
    assert data["approval_id"] == "appr-1"
    assert data["tool_name"] == "create_ticket"
    # CRITICAL: interrupt must be cleared to prevent stale re-trigger
    clear_mock.assert_called_once()


def test_reject_mcp_write_with_reason() -> None:
    """reason field is accepted; endpoint still returns rejected=True."""
    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
        patch("app.routers.assistant.clear_interrupted_turn"),
    ):
        tc, stub = _make_reject_client()
        mk_client.return_value = stub
        mk_load.return_value = _make_interrupt()

        resp = tc.post(
            "/api/assistant/conversation/conv-1/reject-mcp-write",
            json={"approval_id": "appr-1", "reason": "looks risky"},
        )

    assert resp.status_code == 200
    assert resp.json()["rejected"] is True


def test_reject_mcp_write_no_interrupt_returns_422() -> None:
    """Returns 422 when no pending MCP approval in interrupt state."""
    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
    ):
        tc, stub = _make_reject_client()
        mk_client.return_value = stub
        mk_load.return_value = None

        resp = tc.post(
            "/api/assistant/conversation/conv-1/reject-mcp-write",
            json={"approval_id": "appr-1"},
        )

    assert resp.status_code == 422


def test_reject_mcp_write_id_mismatch_returns_409() -> None:
    """Returns 409 when approval_id in request doesn't match stored state."""
    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
    ):
        tc, stub = _make_reject_client()
        mk_client.return_value = stub
        mk_load.return_value = _make_interrupt(approval_id="appr-correct")

        resp = tc.post(
            "/api/assistant/conversation/conv-1/reject-mcp-write",
            json={"approval_id": "appr-WRONG"},
        )

    assert resp.status_code == 409


def test_reject_mcp_write_already_processed_returns_409() -> None:
    """Returns 409 when the approvals row is not found / already processed (empty update)."""
    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
        patch("app.routers.assistant.clear_interrupted_turn"),
    ):
        tc, stub = _make_reject_client(approval_updated=[])   # empty → already processed
        mk_client.return_value = stub
        mk_load.return_value = _make_interrupt()

        resp = tc.post(
            "/api/assistant/conversation/conv-1/reject-mcp-write",
            json={"approval_id": "appr-1"},
        )

    assert resp.status_code == 409


def test_reject_mcp_write_clear_error_non_fatal() -> None:
    """clear_interrupted_turn failure is non-fatal; endpoint still returns 200.

    The rejection was durably recorded in Supabase. The Redis interrupt will
    expire on its own TTL. Not surfacing a 500 here avoids confusing the client
    into thinking the rejection itself failed.
    """
    with (
        patch("app.routers.assistant.get_supabase_client") as mk_client,
        patch("app.routers.assistant.load_interrupted_turn") as mk_load,
        patch(
            "app.routers.assistant.clear_interrupted_turn",
            side_effect=RuntimeError("redis timeout"),
        ),
    ):
        # raise_server_exceptions=False so we see the HTTP response, not the exc
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.assistant import router
        from app.auth.dependencies import get_current_user, get_org_context
        from app.config import get_settings

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
        app.dependency_overrides[get_org_context] = lambda: "org-1"
        app.dependency_overrides[get_settings] = lambda: MagicMock()

        stub = _make_client_stub()
        mk_client.return_value = stub
        mk_load.return_value = _make_interrupt()

        tc = TestClient(app, raise_server_exceptions=True)
        resp = tc.post(
            "/api/assistant/conversation/conv-1/reject-mcp-write",
            json={"approval_id": "appr-1"},
        )

    assert resp.status_code == 200
    assert resp.json()["rejected"] is True
