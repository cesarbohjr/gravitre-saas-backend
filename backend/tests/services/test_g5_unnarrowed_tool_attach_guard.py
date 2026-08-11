"""G5 standing CI — no unnarrowed tool attach to the model."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.services.agent_platform_optimizer import narrow_tools_for_turn
from app.services.narrowed_tools import NarrowedTools, assert_tools_narrowed, mark_narrowed
from app.services.tool_registry import get_tool_registry


REPO_BACKEND = Path(__file__).resolve().parents[2]


def test_narrow_tools_returns_narrowed_tools_marker():
    registry = get_tool_registry()
    tools = registry.get_tools_for_agent(["*"], ["apollo", "hubspot", "platform"])
    assert len(tools) > 40  # catalog large enough that unnarrowed would be unsafe
    narrowed, stats = narrow_tools_for_turn(
        tools,
        query="add contacts to my apollo list",
        connected_integrations=["apollo", "hubspot"],
        max_tools=28,
    )
    assert isinstance(narrowed, NarrowedTools)
    assert narrowed.gravitre_narrowed is True
    assert stats["visibleTools"] <= 28
    assert len(narrowed) == stats["visibleTools"]
    assert_tools_narrowed(narrowed, where="test")


def test_assert_tools_narrowed_blocks_plain_list():
    plain = [{"type": "function", "function": {"name": "x", "parameters": {}}}]
    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        assert_tools_narrowed(plain, where="unit")


def test_react_chat_with_tools_requires_narrowed(monkeypatch):
    """Agent-jobs / ReAct attach path refuses a raw catalog list."""
    import asyncio

    from app.operators.react_engine import ReActEngine
    from app.services.tool_registry import ToolRegistry

    engine = ReActEngine(settings=None, registry=ToolRegistry())

    class _FakeRouter:
        _openai = object()

    engine.router = _FakeRouter()  # type: ignore[assignment]
    plain = [{"type": "function", "function": {"name": "hubspot_lists_create", "parameters": {}}}]
    monkeypatch.setattr(
        "app.operators.react_engine._supports_custom_temperature",
        lambda _m: False,
    )

    async def _run():
        await engine._chat_with_tools(
            [{"role": "user", "content": "hi"}], plain, "gpt-4o-mini"
        )

    with pytest.raises(RuntimeError, match="unnarrowed_tool_attach_blocked"):
        asyncio.run(_run())


def test_agent_job_react_path_narrows_under_cap():
    """Evidence: same narrow used by agent_jobs → ReAct before model attach."""
    registry = get_tool_registry()
    all_tools = registry.get_tools_for_agent(
        ["*"], ["apollo", "hubspot", "clay", "slack", "gmail", "platform"]
    )
    narrowed, stats = narrow_tools_for_turn(
        all_tools,
        query="enrich MSP Prospects and add to HubSpot",
        connected_integrations=["apollo", "hubspot", "clay"],
        max_tools=28,
    )
    assert stats["totalTools"] == len(all_tools)
    assert stats["visibleTools"] <= 28
    assert stats["visibleTools"] < stats["totalTools"]
    # Action ids in the narrowed set must be real registry tools (not stale names).
    names = {
        str((t.get("function") or {}).get("name") or "")
        for t in narrowed
        if isinstance(t, dict)
    }
    assert names
    for name in names:
        assert name in registry._specs or name.startswith("mcp_")  # noqa: SLF001


def test_no_raw_completions_create_with_tools_outside_allowlist():
    """Static guard: chat.completions.create(..., tools=) only in known chokepoints."""
    allow = {
        "operators/react_engine.py",
        "services/unified_turn_reasoning_service.py",
        "services/providers/openai_adapter.py",
        "services/providers/provider_tool_router.py",
    }
    offenders: list[str] = []
    for path in (REPO_BACKEND / "app").rglob("*.py"):
        rel = path.relative_to(REPO_BACKEND / "app").as_posix()
        if rel in allow:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = ""
            if isinstance(func, ast.Attribute) and func.attr == "create":
                # *.chat.completions.create
                val = func.value
                if (
                    isinstance(val, ast.Attribute)
                    and val.attr == "completions"
                    and isinstance(val.value, ast.Attribute)
                    and val.value.attr == "chat"
                ):
                    name = "chat.completions.create"
            if name != "chat.completions.create":
                continue
            for kw in node.keywords:
                if kw.arg == "tools":
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "New chat.completions.create(tools=...) site must use NarrowedTools / "
        f"assert_tools_narrowed. Offenders: {offenders}"
    )


def test_mark_narrowed_passthrough():
    n = mark_narrowed([{"type": "function", "function": {"name": "a"}}], source="t")
    assert isinstance(n, NarrowedTools)
    assert n.as_openai_tools()[0]["function"]["name"] == "a"
