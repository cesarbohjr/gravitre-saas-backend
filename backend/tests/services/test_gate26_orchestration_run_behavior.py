"""Gate 26 executable orchestration-run persistence and failure contracts."""
from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.services import chat_orchestration_runs as runs


def test_late_run_create_exception_returns_none_without_approval_or_steps(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic persistence outage")

    step = Mock()
    approval = Mock()
    monkeypatch.setattr(runs, "create_run", fail)
    monkeypatch.setattr(runs, "create_step", step)
    monkeypatch.setattr(runs, "create_contract_approval", approval)
    result = runs.start_orchestration_run(
        object(), org_id="org-test", user_id="user-test",
        conversation_id="conversation-test", goal="synthetic",
        steps=[{"step_id": "step-1", "label": "Read"}],
    )
    assert result is None
    step.assert_not_called()
    approval.assert_not_called()


def test_missing_persisted_run_id_returns_none_without_side_effects(monkeypatch):
    monkeypatch.setattr(runs, "create_run", lambda *a, **kw: {})
    step = Mock()
    approval = Mock()
    monkeypatch.setattr(runs, "create_step", step)
    monkeypatch.setattr(runs, "create_contract_approval", approval)
    assert runs.start_orchestration_run(
        object(), org_id="org-test", user_id="user-test",
        conversation_id="conversation-test", goal="synthetic",
        steps=[{"step_id": "step-1"}],
    ) is None
    step.assert_not_called()
    approval.assert_not_called()


def test_read_write_graph_preserves_order_and_action_arguments():
    steps, nodes, edges = runs._chat_orch_graph_from_steps([
        {"step_id": "read", "label": "Read", "plan": {"invoke_action": "get", "args": {"limit": 2}}},
        {"step_id": "write", "label": "Write", "plan": {"invoke_action": "create", "args": {"dry_run": True}}},
    ])
    assert [s["id"] for s in steps] == ["read", "write"]
    assert nodes[0]["config"]["limit"] == 2
    assert nodes[1]["config"]["dry_run"] is True
    assert edges == [{"from": "read", "to": "write", "from_node_id": "read", "to_node_id": "write"}]
