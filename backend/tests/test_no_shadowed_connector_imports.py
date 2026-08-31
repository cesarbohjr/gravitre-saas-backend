"""Guard against a connector symbol being silently rebound by a later import.

Found while building the api_reference map: tool_service imported ``list_invoices``
from quickbooks and again from stripe_api, so quickbooks.invoices.list called
Stripe's function and raised TypeError on every invocation. Same for jira's
get_issue / update_issue, both shadowed by github_api. Python rebinds silently.

``create_issue as jira_create_issue`` already existed in the same import block,
which means this collision was hit before and fixed one instance at a time. This
test makes it structural instead.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


def _shadowed(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bound: dict[str, tuple[str, int]] = {}
    problems: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        for alias in node.names:
            if alias.asname:
                continue
            prev = bound.get(alias.name)
            if prev and prev[0] != node.module:
                problems.append(
                    f"{path.name}: '{alias.name}' from {prev[0]} (line {prev[1]}) "
                    f"is shadowed by {node.module} (line {node.lineno}); "
                    f"alias one of them"
                )
            bound[alias.name] = (node.module, node.lineno)
    return problems


def test_no_module_level_import_shadowing() -> None:
    problems: list[str] = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        try:
            problems.extend(_shadowed(path))
        except SyntaxError:
            continue
    assert not problems, "shadowed connector imports:\n" + "\n".join(problems)


@pytest.mark.parametrize(
    ("symbol", "expected_module"),
    [
        ("quickbooks_list_invoices", "app.connectors.quickbooks"),
        ("list_invoices", "app.connectors.stripe_api"),
        ("jira_get_issue", "app.connectors.jira"),
        ("jira_update_issue", "app.connectors.jira"),
        ("get_issue", "app.connectors.github_api"),
        ("update_issue", "app.connectors.github_api"),
    ],
)
def test_previously_shadowed_symbols_resolve_to_their_own_vendor(
    symbol: str, expected_module: str
) -> None:
    from app.services import tool_service

    fn = getattr(tool_service, symbol)
    assert fn.__module__ == expected_module


@pytest.mark.parametrize(
    ("executor", "callee", "sample_kwargs"),
    [
        (
            "_exec_quickbooks_invoices_list",
            "quickbooks_list_invoices",
            {"max_results": 25, "start_position": 1},
        ),
        ("_exec_jira_issues_get", "jira_get_issue", {"fields": None}),
    ],
)
def test_executor_call_signature_accepts_what_the_executor_passes(
    executor: str, callee: str, sample_kwargs: dict
) -> None:
    """The original bug was a TypeError, not a wrong result. Bind the exact
    keywords the executor uses against the resolved callee's signature."""
    from app.services import tool_service

    fn = getattr(tool_service, callee)
    sig = inspect.signature(fn)
    positional = [p for p in sig.parameters.values() if p.kind is p.POSITIONAL_OR_KEYWORD]
    args = ["x"] * len([p for p in positional if p.default is p.empty])
    sig.bind(*args, **sample_kwargs)
