"""Find import names that are silently rebound by a later import in the same module.

Motivation: building the api_reference map turned up quickbooks.invoices.list as
unmappable, and the reason was not an extractor limitation — tool_service imports
``list_invoices`` from app.connectors.quickbooks and then again from
app.connectors.stripe_api, so the QuickBooks executor calls Stripe's function.
Python rebinds silently, no linter in this repo flags it, and the action fails at
runtime with a TypeError on the first unexpected keyword.

This is a class-level check, not a one-off: any module that imports the same
symbol name from two different connectors has the same defect.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8")


def shadowed(path: Path) -> list[tuple[str, str, int, str, int]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    # name -> (module, lineno) of the binding currently in effect
    seen: dict[str, tuple[str, int]] = {}
    hits: list[tuple[str, str, int, str, int]] = []
    for node in tree.body:  # module level only; that is where rebinding bites
        if not isinstance(node, ast.ImportFrom) or node.module is None:
            continue
        for alias in node.names:
            name = alias.asname or alias.name
            if alias.asname:
                continue  # explicitly disambiguated
            prev = seen.get(name)
            if prev and prev[0] != node.module:
                hits.append((name, prev[0], prev[1], node.module, node.lineno))
            seen[name] = (node.module, node.lineno)
    return hits


def main() -> int:
    total = 0
    for path in sorted((BACKEND / "app").rglob("*.py")):
        hits = shadowed(path)
        if not hits:
            continue
        rel = path.relative_to(BACKEND).as_posix()
        print(f"\n{rel}")
        for name, mod_a, line_a, mod_b, line_b in hits:
            total += 1
            print(f"  {name}")
            print(f"     shadowed : {mod_a} (line {line_a})")
            print(f"     winner   : {mod_b} (line {line_b})")
    print(f"\nshadowed import bindings: {total}")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
