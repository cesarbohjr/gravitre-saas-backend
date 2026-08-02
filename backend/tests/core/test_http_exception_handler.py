"""HTTP exception payload must stay human-readable (no Python dict repr)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.errors import _normalize_detail, http_exception_handler
from app.workflows.policy import active_run_conflict_detail


def test_normalize_detail_preserves_active_run_conflict_message():
    detail = active_run_conflict_detail("a4886eb2-1111-2222-3333-444444444444")
    message, code, details = _normalize_detail(detail)
    assert "run in progress" in message
    assert "a4886eb2" in message
    assert "{" not in message
    assert details["active_run_id"] == "a4886eb2-1111-2222-3333-444444444444"
    assert code == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_http_exception_handler_returns_plain_error_string():
    request = Request({"type": "http", "method": "POST", "path": "/api/workflows/execute", "headers": []})
    exc = HTTPException(
        status_code=409,
        detail=active_run_conflict_detail("a4886eb2-1111-2222-3333-444444444444"),
    )
    response = await http_exception_handler(request, exc)
    body = response.body.decode()
    assert response.status_code == 409
    assert "a4886eb2" in body
    assert "{'message'" not in body
    assert '"active_run_id"' in body
