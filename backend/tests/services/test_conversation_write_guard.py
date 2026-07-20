"""Hard guard: test credentials default-deny outside the isolated org."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.conversation_write_guard import (
    DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
    DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
    FORBIDDEN_OPERATOR_ORG_ID,
    ConversationWriteBlockedError,
    assert_conversation_create_allowed,
    assert_org_write_allowed,
    clear_request_actor,
    is_conversation_write_restricted,
    is_restricted_test_credential,
    is_smoke_test_ci_context,
    mark_smoke_run,
    set_smoke_run_context,
)


@pytest.fixture(autouse=True)
def _clear_smoke_flags(monkeypatch):
    monkeypatch.delenv("GRAVITREE_SMOKE_RUN", raising=False)
    monkeypatch.delenv("GRAVITREE_CONVERSATION_SMOKE", raising=False)
    set_smoke_run_context(False)
    clear_request_actor()
    yield
    set_smoke_run_context(False)
    clear_request_actor()
    monkeypatch.delenv("GRAVITREE_SMOKE_RUN", raising=False)
    monkeypatch.delenv("GRAVITREE_CONVERSATION_SMOKE", raising=False)


def test_real_user_unflagged_allows_customer_org():
    """Real customer traffic must not be blocked."""
    assert not is_smoke_test_ci_context()
    assert not is_restricted_test_credential(actor_id="f7e32f06-49df-4e73-8962-f41c21850762")
    assert_conversation_create_allowed(
        FORBIDDEN_OPERATOR_ORG_ID,
        actor_id="f7e32f06-49df-4e73-8962-f41c21850762",
        actor_email="cesar@gravitre.app",
    )


def test_smoke_sa_unflagged_refuses_customer_org():
    """Default-deny: forgetting mark_smoke_run() must still refuse."""
    assert not is_smoke_test_ci_context()
    assert is_restricted_test_credential(actor_id=DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID)
    with pytest.raises(ConversationWriteBlockedError, match="REFUSING conversation create"):
        assert_conversation_create_allowed(
            FORBIDDEN_OPERATOR_ORG_ID,
            actor_id=DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
            actor_email="conversation-smoke-sa@gravitre.app",
        )


def test_smoke_sa_allows_isolated_org_without_flag():
    assert_conversation_create_allowed(
        DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
        actor_id=DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        actor_email="conversation-smoke-sa@gravitre.app",
    )


def test_smoke_flag_refuses_even_with_real_user_jwt():
    mark_smoke_run()
    assert is_conversation_write_restricted(actor_id="f7e32f06-49df-4e73-8962-f41c21850762")
    with pytest.raises(ConversationWriteBlockedError):
        assert_conversation_create_allowed(
            FORBIDDEN_OPERATOR_ORG_ID,
            actor_id="f7e32f06-49df-4e73-8962-f41c21850762",
        )


def test_smoke_context_allows_isolated_org_only():
    mark_smoke_run()
    assert_conversation_create_allowed(DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID)
    with pytest.raises(ConversationWriteBlockedError, match="REFUSING conversation create"):
        assert_conversation_create_allowed(FORBIDDEN_OPERATOR_ORG_ID)


def test_assert_org_write_allowed_covers_tool_invoke_resource():
    """Module 0 generalized choke — same allow-list for invoke_tool / Meson / platform."""
    assert_org_write_allowed(
        DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID,
        actor_id=DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
        resource="tool invoke",
    )
    with pytest.raises(ConversationWriteBlockedError, match="REFUSING tool invoke"):
        assert_org_write_allowed(
            FORBIDDEN_OPERATOR_ORG_ID,
            actor_id=DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
            resource="tool invoke",
        )


@pytest.mark.asyncio
async def test_ensure_owned_conversation_raises_for_sa_wrong_org_without_flag():
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

    service = ConversationStateService()
    with pytest.raises(ConversationWriteBlockedError):
        await service.ensure_owned_conversation(
            org_id=FORBIDDEN_OPERATOR_ORG_ID,
            user_id=DEFAULT_ISOLATED_CONVERSATION_TEST_USER_ID,
            conversation_id="11111111-1111-1111-1111-111111111111",
            title="should fail unflagged",
            client=client,
        )
