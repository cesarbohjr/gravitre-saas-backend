"""Contract tests for the governed general Playwright planner.

No real browser or provider calls occur here. Live certification must still
prove authorization and independent external write behavior.
"""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import patch

from native_workers.playwright_recovery import proposal


def _observation():
    return SimpleNamespace(url="https://example.com/",
        dom_state=SimpleNamespace(llm_representation=lambda:'{"nodes":[]}'))


def test_planner_accepts_exact_bounded_dom_action():
    def fake_gateway(*_):
        return {"choices":[{"message":{"content":'{"action":"click","index":1}'}}]}
    with patch("native_workers.playwright_recovery.gateway",fake_gateway):
        assert proposal({"model":"test"},_observation(),"check task")=={"action":"click","index":1}


def test_planner_rejects_unobserved_or_privileged_actions():
    import pytest
    for content in ('{"action":"script","code":"alert(1)"}',
                    '{"action":"click","index":0}',
                    '{"action":"fill","index":2,"value":"x","extra":true}'):
        with patch("native_workers.playwright_recovery.gateway",
                   lambda *_:{"choices":[{"message":{"content":content}}]}):
            with pytest.raises(PermissionError):
                proposal({"model":"test"},_observation(),"check task")
