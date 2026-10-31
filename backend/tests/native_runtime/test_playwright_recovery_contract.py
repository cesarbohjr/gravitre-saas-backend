"""Offline planner contract tests without SDK/container dependencies."""
import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def planner_with(reply):
    source=Path(__file__).resolve().parents[2] / "native-workers" / "playwright_recovery.py"
    tree=ast.parse(source.read_text())
    fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="proposal")
    ns={"json":json,"gateway":lambda *_:{"choices":[{"message":{"content":reply}}]}}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),"exec"),ns)
    return ns["proposal"]


def observation():
    return SimpleNamespace(url="https://example.com/",
        dom_state=SimpleNamespace(llm_representation=lambda:'{"nodes":[]}'))


def test_planner_accepts_bounded_dom_action():
    assert planner_with('{"action":"click","index":1}')(
        {"model":"test"},observation(),"task")=={"action":"click","index":1}


@pytest.mark.parametrize("reply",[
    '{"action":"script","code":"alert(1)"}',
    '{"action":"click","index":0}',
    '{"action":"fill","index":2,"value":"x","extra":true}',
])
def test_planner_rejects_invalid_actions(reply):
    with pytest.raises(PermissionError):
        planner_with(reply)({"model":"test"},observation(),"task")
