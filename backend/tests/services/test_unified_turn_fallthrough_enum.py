"""F10 — fallthrough_reason enum exhaustiveness + pattern matrix."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.services.unified_turn_classical_fallback import (
    _MESSAGE_TOOL_SSE_PATTERNS,
    message_requires_classical_tool_sse,
    should_defer_unified_turn_live_to_classical,
)
from app.services.unified_turn_fallthrough import (
    LIVE_FALLTHROUGH_REASONS,
    assert_known_fallthrough_reason,
    is_known_fallthrough_reason,
)


def test_known_exact_reasons():
    for reason in LIVE_FALLTHROUGH_REASONS:
        assert is_known_fallthrough_reason(reason)
        assert assert_known_fallthrough_reason(reason) == reason


def test_dynamic_prefixes_allowed():
    assert is_known_fallthrough_reason("outcome_skipped")
    assert is_known_fallthrough_reason("unhandled_kind_foo")
    assert not is_known_fallthrough_reason("invented_reason")
    with pytest.raises(ValueError):
        assert_known_fallthrough_reason("invented_reason")


def test_source_mark_live_fallthrough_reasons_are_known():
    """Scan apply_unified_turn_live source for _mark_live_fallthrough string literals."""
    path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "services"
        / "unified_turn_reasoning_service.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name == "_mark_live_fallthrough" and len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    found.add(arg.value)
                elif isinstance(arg, ast.JoinedStr):
                    # f"outcome_{...}" / f"unhandled_kind_{...}"
                    if arg.values and isinstance(arg.values[0], ast.Constant):
                        prefix = str(arg.values[0].value)
                        if prefix.startswith("outcome_"):
                            found.add("outcome_skipped")
                        if prefix.startswith("unhandled_kind_"):
                            found.add("unhandled_kind_x")
            self.generic_visit(node)

    Visitor().visit(tree)
    assert found, "expected at least one _mark_live_fallthrough literal"
    for reason in found:
        assert is_known_fallthrough_reason(reason), reason


# Every remaining safety-net pattern: one positive + one negative.
_PATTERN_CASES: list[tuple[str, str, bool]] = [
    (r"connectors.*connected", "What connectors are connected right now?", True),
    (r"connectors.*connected", "hello there", False),
    (r"what connectors", "what connectors do we have", True),
    (r"what connectors", "connectors maybe later", False),
    (r"getconnectorstatus", "getConnectorStatus please", True),
    (r"getconnectorstatus", "connector status please", False),
    (r"refund policy", "What is the refund policy?", True),
    (r"refund policy", "policy about shipping", False),
    (r"internal knowledge", "internal org knowledge on X", True),
    (r"internal knowledge", "external wiki", False),
    (r"fictional subsidiary", "fictional subsidiary Acme", True),
    (r"fictional subsidiary", "real subsidiary", False),
    (r"zephyr dynamics", "Zephyr Dynamics facts", True),
    (r"zephyr dynamics", "dynamics of growth", False),
    (r"outline.*plan.*tools", "outline a plan before tools", True),
    (r"outline.*plan.*tools", "outline my day", False),
    (r"plan.*before.*tools", "plan before tools please", True),
    (r"plan.*before.*tools", "plan the picnic", False),
    (r"post slack message", "post a slack message to #ops", True),
    (r"post slack message", "slack is useful", False),
    (r"create apollo contact list", "create an apollo contact list", True),
    (r"create apollo contact list", "apollo pricing", False),
    (r"searchknowledgebase", "SearchKnowledgeBase refund", True),
    (r"searchknowledgebase", "search knowledge base", False),
]


@pytest.mark.parametrize("label,message,expected", _PATTERN_CASES)
def test_defer_pattern_matrix(label: str, message: str, expected: bool):
    _ = label
    assert message_requires_classical_tool_sse(message) is expected


def test_f2_removed_bare_vendor_patterns_absent():
    sources = "\n".join(p.pattern for p in _MESSAGE_TOOL_SSE_PATTERNS)
    assert r"\bapollo\b" not in sources
    assert r"\bslack\b" not in sources
    assert r"\bcontact lists?\b" not in sources
    assert r"\bknowledge base\b" not in sources


def test_needs_tool_sse_structured_defer():
    assert should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="anything about apollo",
        needs_tool_sse=True,
    )
    assert not should_defer_unified_turn_live_to_classical(
        mode_key="fast",
        outcome_kind="conversational_reply",
        message="anything about apollo",
        needs_tool_sse=False,
    )
