"""Find every place a NarrowedTools value gets rebuilt and loses its proof.

Structural cause of `unnarrowed_tool_attach_blocked`: the narrowing proof is an
attribute on a `list` subclass, so `list(x)`, a comprehension over `x`, a slice
`x[:]`, `copy()` and `sorted()` all return a plain `list` and discard it
silently.

The scan is intraprocedural and name-based, which is the honest bound: it tracks
names assigned from a known narrowing producer within a single function, then
reports where those names are rebuilt. It does NOT follow values across function
boundaries or through containers.

Findings are classified, because most rebuilds are harmless:

  ATTACH    the rebuilt value can reach a model attach site -> real defect
  REMARKED  rebuilt, then re-marked via mark_narrowed / a producer -> safe
  MEASURE   rebuilt only as an argument to a sizing/logging helper -> safe

Run:  python scripts/scan_narrowed_tools_strips.py
"""
from __future__ import annotations

import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "backend" / "app"

# Calls whose return value carries the narrowing proof.
PRODUCERS = {
    "narrow_tools_for_turn",
    "embed_narrow_tools_for_turn",
    "mark_narrowed",
    "apply_progressive_disclosure",
    "as_openai_tools",
}

# Calls that consume tools but only to size or describe them.
MEASURERS = {"payload_bytes", "len", "json", "dumps", "sorted_names", "repr", "str"}

# Where an unnarrowed list actually causes the failure.
ATTACH_SINKS = {"complete_with_tools", "create", "_complete_unified_turn"}

SELF_EXEMPT = {"narrowed_tools.py"}  # defines the conversion; rebuilding is its job

# Populated at scan time: functions that re-mark narrowed input.
PRESERVERS: set[str] = set()


@dataclass
class Finding:
    path: str
    line: int
    func: str
    name: str
    how: str
    verdict: str
    detail: str = ""


@dataclass
class FuncScan:
    name: str
    narrowed: set[str] = field(default_factory=set)
    remarked_lines: dict[str, list[int]] = field(default_factory=dict)


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        f = node.func
        if isinstance(f, ast.Name):
            return f.id
        if isinstance(f, ast.Attribute):
            return f.attr
    return ""


def _targets(node: ast.Assign | ast.AnnAssign) -> list[str]:
    out: list[str] = []
    tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
    for t in tgts:
        if isinstance(t, ast.Name):
            out.append(t.id)
        elif isinstance(t, ast.Tuple):
            for e in t.elts:
                if isinstance(e, ast.Name):
                    out.append(e.id)
    return out


def _tool_targets(node: ast.Assign | ast.AnnAssign) -> list[str]:
    """Only the names that actually receive tools.

    Producers return tuples like (tools, stats) or (tools, full_by_name,
    loaded_names). Treating every unpacked name as narrowed produced a false
    ATTACH on `sorted(loaded_names)`, which is a set of tool NAMES, not tools.
    """
    tgts = node.targets if isinstance(node, ast.Assign) else [node.target]
    for t in tgts:
        if isinstance(t, ast.Name):
            return [t.id]
        if isinstance(t, ast.Tuple) and t.elts:
            first = t.elts[0]
            return [first.id] if isinstance(first, ast.Name) else []
    return []


def scan_function(fn: ast.FunctionDef | ast.AsyncFunctionDef, path: Path) -> list[Finding]:
    scan = FuncScan(name=fn.name)

    # Pass 1: which local names hold a narrowed value, and where they are re-marked.
    for node in ast.walk(fn):
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            call = _call_name(node.value)
            if call in PRODUCERS:
                for n in _tool_targets(node):
                    scan.narrowed.add(n)
                    scan.remarked_lines.setdefault(n, []).append(node.lineno)

    if not scan.narrowed:
        return []

    findings: list[Finding] = []

    def _rebuilt_names(value: ast.AST) -> list[tuple[str, str]]:
        """Names of narrowed values that `value` strips, with the mechanism."""
        hits: list[tuple[str, str]] = []
        if isinstance(value, ast.Call) and _call_name(value) in {"list", "sorted", "copy"}:
            for a in value.args:
                base = a
                if isinstance(base, ast.BoolOp) and base.values:
                    base = base.values[0]
                if isinstance(base, ast.Name) and base.id in scan.narrowed:
                    hits.append((base.id, f"{_call_name(value)}()"))
        if isinstance(value, ast.ListComp):
            for gen in value.generators:
                it = gen.iter
                if isinstance(it, ast.Name) and it.id in scan.narrowed:
                    hits.append((it.id, "comprehension"))
        if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Slice):
            if isinstance(value.value, ast.Name) and value.value.id in scan.narrowed:
                hits.append((value.value.id, "slice"))
        return hits

    for node in ast.walk(fn):
        # Rebuild assigned to a name -> the dangerous shape.
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            outer = _call_name(node.value)
            if outer in PRODUCERS:
                continue  # re-marked in the same expression; safe by construction
            for name, how in _rebuilt_names(node.value):
                tgt = ", ".join(_targets(node)) or "<expr>"
                # Re-marked later in the function under the same name?
                later = [
                    ln for ln in scan.remarked_lines.get(tgt, []) if ln > node.lineno
                ]
                verdict = "REMARKED" if later else "ATTACH"
                detail = f"-> {tgt}" + (f"; re-marked at line {later[0]}" if later else "")
                findings.append(
                    Finding(
                        str(path.relative_to(ROOT)), node.lineno, fn.name, name, how,
                        verdict, detail,
                    )
                )

        # Rebuild passed straight into a call.
        if isinstance(node, ast.Call):
            callee = _call_name(node)
            if callee in PRODUCERS:
                continue
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                for name, how in _rebuilt_names(arg):
                    if callee in PRESERVERS:
                        verdict = "BLINDS_PRESERVER"
                    elif callee in MEASURERS:
                        verdict = "MEASURE"
                    elif callee in ATTACH_SINKS:
                        verdict = "ATTACH"
                    else:
                        verdict = "REMARKED"
                    findings.append(
                        Finding(
                            str(path.relative_to(ROOT)), node.lineno, fn.name, name,
                            how, verdict, f"-> {callee}()",
                        )
                    )

    return findings


def collect_preservers(trees: dict[Path, ast.Module]) -> set[str]:
    """Functions that re-mark narrowed input -- and so must not be fed a strip.

    `_stable_tool_list` checks `isinstance(tools, NarrowedTools)` and re-marks,
    but its caller passed `list(visible or [])`, so the check never saw a
    NarrowedTools and the preserve-branch was dead code. Feeding a stripped
    value to a preserver is silently self-defeating, so it gets its own verdict.
    """
    found: set[str] = set()
    for tree in trees.values():
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = ast.dump(fn)
            if "mark_narrowed" in body and (
                "gravitre_narrowed" in body or "NarrowedTools" in body
            ):
                found.add(fn.name)
    return found


def main() -> int:
    trees: dict[Path, ast.Module] = {}
    for path in sorted(APP.rglob("*.py")):
        if path.name in SELF_EXEMPT:
            continue
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue

    global PRESERVERS
    PRESERVERS = collect_preservers(trees) - PRODUCERS
    print(f"preserver functions detected: {sorted(PRESERVERS)}\n")

    all_findings: list[Finding] = []
    scanned = len(trees)
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                all_findings.extend(scan_function(node, path))

    print(f"scanned {scanned} files under backend/app\n")
    if not all_findings:
        print("no NarrowedTools rebuilds found at all")
        return 0

    for verdict in ("ATTACH", "BLINDS_PRESERVER", "REMARKED", "MEASURE"):
        rows = [f for f in all_findings if f.verdict == verdict]
        print(f"== {verdict}: {len(rows)} ==")
        for f in rows:
            print(f"  {f.path}:{f.line}  {f.func}()  {f.name} via {f.how}  {f.detail}")
        print()

    bad = [f for f in all_findings if f.verdict in {"ATTACH", "BLINDS_PRESERVER"}]
    if bad:
        print(f"FAIL: {len(bad)} rebuild(s) reach an attach site or blind a preserver")
        return 1
    print("PASS: no rebuild reaches an attach site or blinds a preserver")
    return 0


if __name__ == "__main__":
    sys.exit(main())
