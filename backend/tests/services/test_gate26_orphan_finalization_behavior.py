"""Gate 26: executable orphan-finalization regression (synthetic, no DB/provider)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.services import chat_orchestration_service as service


@pytest.mark.asyncio
@pytest.mark.parametrize("steps,late_id,expected_orphan", [
    ([], None, True),
    ([{"step_id": "s1", "label": "Read"}], None, True),
    ([{"step_id": "s1", "label": "Read"}], "run-late", False),
])
async def test_orphan_finalization_dispatches_to_one_terminal_owner(
    monkeypatch, steps, late_id, expected_orphan
):
    """Exercise real async finalizer until state update; assert persisted vs orphan owner.

    All external fanout and storage are mocked. This does not certify durability.
    """
    outcome = SimpleNamespace(consequential=0, as_dict=lambda: {})
    monkeypatch.setattr(service, "orchestration_terminal_status", lambda rows: "failed")
    monkeypatch.setattr(service, "orchestration_outcome", lambda rows: outcome)
    monkeypatch.setattr(service, "orchestration_run_fully_completed", lambda rows: False)
    start = Mock(return_value=late_id)
    persisted = Mock()
    orphan = Mock()
    monkeypatch.setattr(service, "start_orchestration_run", start)
    monkeypatch.setattr(service, "finalize_orchestration_run", persisted)
    # Orphan finalization imports this function locally; patch the defining module.
    from app.services import execution_outcome
    monkeypatch.setattr(execution_outcome, "finalize_execution_outcome", orphan)
    monkeypatch.setattr(service, "resolve_orchestration_result_url", lambda **kw: None)
    monkeypatch.setattr(service, "first_external_step_url", lambda *a, **kw: None)
    state = SimpleNamespace(update_task_state=AsyncMock(side_effect=RuntimeError("stop-after-terminal")))
    instance = object.__new__(service.ChatOrchestrationService)
    instance._state = state
    instance.settings = SimpleNamespace()
    params = {"steps": steps, "step_results": [], "goal": "synthetic"}
    with pytest.raises(RuntimeError, match="stop-after-terminal"):
        await instance._finalize_orchestration("conversation-test", "org-test", "user-test", params, object())
    if steps:
        start.assert_called_once()
    else:
        start.assert_not_called()
    if expected_orphan:
        orphan.assert_called_once()
        persisted.assert_not_called()
        assert orphan.call_args.kwargs["persist_run"] is False
        assert orphan.call_args.kwargs["metadata"]["path"] == "chat_orchestration_orphan"
    else:
        persisted.assert_called_once()
        orphan.assert_not_called()
        assert persisted.call_args.kwargs["run_id"] == "run-late"
