"""Knowledge sync route permission tests (STA-279)."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.auth.platform_admin import (
    can_trigger_knowledge_sync,
    is_org_admin_role,
    is_org_member_role,
)


def test_org_member_roles():
    assert is_org_member_role("member") is True
    assert is_org_member_role("viewer") is True
    assert is_org_admin_role("member") is False


def test_knowledge_sync_trigger_roles():
    assert can_trigger_knowledge_sync("member") is True
    assert can_trigger_knowledge_sync("admin") is True
    assert can_trigger_knowledge_sync("viewer") is False


@pytest.mark.asyncio
async def test_customer_sync_rejects_viewer_full_sync(monkeypatch):
    from app.routers import knowledge_sync as module

    async def fake_handler(*args, **kwargs):
        return {"status": "queued"}

    monkeypatch.setattr(module, "_trigger_connector_sync_handler", fake_handler)

    body = module.KnowledgeSyncRunRequest(fullSync=True)
    member_ctx = ({"user_id": "user-1"}, "org-1", "viewer")

    with pytest.raises(HTTPException) as exc:
        await module.customer_trigger_connector_sync(
            "connector-1",
            body,
            member_ctx,
            settings=object(),
        )
    assert exc.value.status_code == 403
    assert "Viewer" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_customer_sync_rejects_member_full_sync(monkeypatch):
    from app.routers import knowledge_sync as module

    body = module.KnowledgeSyncRunRequest(fullSync=True)
    member_ctx = ({"user_id": "user-1"}, "org-1", "member")

    with pytest.raises(HTTPException) as exc:
        await module.customer_trigger_connector_sync(
            "connector-1",
            body,
            member_ctx,
            settings=object(),
        )
    assert exc.value.status_code == 403
    assert "admin" in str(exc.value.detail).lower()
