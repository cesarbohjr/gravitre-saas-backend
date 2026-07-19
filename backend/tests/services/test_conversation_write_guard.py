"""Hard guard: smoke/CI conversation creates only in the isolated test org."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.conversation_write_guard import (
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
    is_smoke_test_ci_context,
    mark_smoke_run,
    set_smoke_run_context,
)


@pytest.fixture(autouse=True)
def _clear_smoke_flags(monkeypatch):
    monkeypatch.delenv("GRAVITREE_SMOKE_RUN", raising=False)
    monkeypatch.delenv("GRAVITREE_CONVERSATION_SMOKE", raising=False)
    set_smoke_run_context(False)
    yield
    set_smoke_run_context(False)
    monkeypatch.delenv("GRAVITREE_SMOKE_RUN", raising=False)
    monkeypatch.delenv("GRAVITREE_CONVERSATION_SMOKE", raising=False)


def test_unflagged_context_allows_any_org():
    assert not is_smoke_test_ci_context()
    assert_conversation_create_allowed(FORBIDDEN_OPERATOR_ORG_ID)
    assert_conversation_create_allowed("any-org")


def test_smoke_context_allows_isolated_org_only():
    mark_smoke_run()
    assert is_smoke_test_ci_context()
    assert_conversation_create_allowed(DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID)
    with pytest.raises(ConversationWriteBlockedError, match="REFUSING conversation create"):
        assert_conversation_create_allowed(FORBIDDEN_OPERATOR_ORG_ID)
    with pytest.raises(ConversationWriteBlockedError):
        assert_conversation_create_allowed("11111111-1111-1111-1111-111111111111")


@pytest.mark.asyncio
async def test_ensure_owned_conversation_raises_for_smoke_wrong_org():
    from app.services.conversation_state_service import ConversationStateService

    class _FakeTable:
        def select(self, *_a, **_k):
            return self

        def eq(self, *_a, **_k):
            return self

        def limit(self, *_a, **_k):
            return self

        def insert(self, *_a, **_k):
            raise AssertionError("insert must not run when guard blocks")

        def execute(self):
            return MagicMock(data=[], error=None)

    client = MagicMock()
    client.table = lambda _name: _FakeTable()

    mark_smoke_run()
    service = ConversationStateService()
    with pytest.raises(ConversationWriteBlockedError):
        await service.ensure_owned_conversation(
            org_id=FORBIDDEN_OPERATOR_ORG_ID,
            user_id="user-1",
            conversation_id="11111111-1111-1111-1111-111111111111",
            title="should fail",
            client=client,
        )
