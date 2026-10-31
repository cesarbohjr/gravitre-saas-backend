"""Exercise the real composer prompt, including shortcut/reconnect outcomes."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services.response_composer import _llm_compose


@pytest.mark.asyncio
@pytest.mark.parametrize("spoken", [False, True])
@pytest.mark.parametrize("kind", ["clarify", "permission", "stopped"])
async def test_repeated_request_reaches_composer_without_granting_authority(spoken, kind):
    request = "Rewrite the welcome note in two sentences."
    router = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content="A fresh reply.")))
    with patch("app.services.model_router.get_model_router", return_value=router):
        await _llm_compose(
            kind=kind, envelope={"success": False, "execution_verified": False},
            user_message=request, spoken=spoken,
            history=[{"role": "user", "content": request},
                     {"role": "assistant", "content": "UNTRUSTED_HISTORY_MARKER"}],
            draft=None, settings=SimpleNamespace(disable_ai=False), org_id="org", compose_fn=None,
        )
    kwargs = router.complete.await_args.kwargs
    system = kwargs["system_prompt"]
    assert "## Current repeated request" in system
    assert "provide the requested content in full" in system
    assert "fresh authorization, approvals, cancellation and idempotency" in system
    assert "AUTHORITATIVE ACTION STATE" in system
    assert "UNTRUSTED_HISTORY_MARKER" not in system
    assert "UNTRUSTED_HISTORY_MARKER" in router.complete.await_args.args[1]


@pytest.mark.asyncio
async def test_assistant_echo_does_not_trigger_composer_repeat_policy():
    router = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(content="A reply.")))
    with patch("app.services.model_router.get_model_router", return_value=router):
        await _llm_compose(
            kind="clarify", envelope={"success": False}, user_message="New request",
            spoken=True, history=[{"role": "assistant", "content": "New request"}],
            draft=None, settings=SimpleNamespace(disable_ai=False), org_id="org", compose_fn=None,
        )
    assert "## Current repeated request" not in router.complete.await_args.kwargs["system_prompt"]
