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


def test_live_runtime_provides_explicit_structured_handoff_decision():
    """ECO-001/011, DEC-001/018: no second wording vote after LIVE adjudication.

    Source contract only; actual deployed routing still requires traced E2E.
    """
    path = (
        Path(__file__).resolve().parents[2]
        / "app" / "services" / "unified_turn_reasoning_service.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    decisions = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if name != "should_defer_unified_turn_live_to_classical":
            continue
        decisions.append(node)
        fields = {kw.arg: kw.value for kw in node.keywords}
        assert "needs_tool_sse" in fields
        value = fields["needs_tool_sse"]
        assert isinstance(value, ast.Call)
        assert isinstance(value.func, ast.Name) and value.func.id == "bool"
        assert value.args and isinstance(value.args[0], ast.Attribute)
        assert value.args[0].attr == "needs_tool_sse"
    assert len(decisions) == 1, "one decision at LIVE/classical handoff source"


def test_read_only_connector_query_probe_is_reconciled_before_structured_handoff():
    """Do not regress classical connector-status lookup when classifier has no write."""
    path = (
        Path(__file__).resolve().parents[2]
        / "app" / "services" / "unified_turn_reasoning_service.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8"))
    probes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else (
            node.func.attr if isinstance(node.func, ast.Attribute) else ""
        )
        if name == "message_requires_classical_tool_sse":
            probes.append(node)
    assert len(probes) == 1
    # The sole probe must not depend on requires_action: connector-status is a
    # read-only request and the classifier may reasonably set that to False.
    source = path.read_text(encoding="utf-8")
    segment = source[source.index("    if (\n        not human_moment\n        and not result.needs_tool_sse", source.index("async def apply_unified_turn_live")):]
    segment = segment[:segment.index("    if human_moment:")]
    assert "classification.get(\"requires_action\")" not in segment
    assert "result.needs_tool_sse = True" in segment
