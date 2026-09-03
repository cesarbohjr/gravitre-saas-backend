#!/usr/bin/env python3
"""Mutation testing for the router department-matching guards.

A guard is worth what it catches. Each mutation below reintroduces a real,
specific way this router has been wrong or could plausibly be "tidied" into
being wrong again, and the suite must fail on every one.

Mutation 1 is the original defect. Mutations 2-4 are the obvious fixes that are
measurably worse than the defect -- the ones a future reader would reach for
without the 1982-message measurement in front of them.

Run:  python scripts/mutate_router_department.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
ROUTER = BACKEND / "app" / "knowledge_fabric" / "router.py"
TESTS = "tests/knowledge_fabric/test_router_department_matching.py"

sys.stdout.reconfigure(encoding="utf-8")

# (name, why it matters, old, new)
MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "naked substring match (the original defect)",
        '"law" fires inside "flawed", "incident" inside "coincident"',
        "    for dept, matchers in _DEPT_MATCHERS.items():\n"
        "        if any(m.search(lower) for m in matchers):",
        "    for dept, matchers in _DEPT_KEYWORDS.items():\n"
        "        if any(m in lower for m in matchers):",
    ),
    (
        "plain word boundary on both sides",
        "the obvious fix; destroys prospects/msps/cybersecurity, 47 good matches",
        '    return re.compile(left + escaped + r"[a-z]*")',
        '    return re.compile(left + escaped + r"(?![a-z0-9])")',
    ),
    (
        "drop the left boundary, keep the suffix",
        "half a fix: accidents return while inflections still work",
        '    left = r"(?<![a-z0-9])"',
        '    left = r""',
    ),
    (
        "exact-only set emptied",
        '"sec" resumes matching secondary/security/cybersecurity',
        '_EXACT_ONLY_KEYWORDS = frozenset(\n'
        '    {"sec", "seo", "ftc", "csf", "gaap", "xbrl", "eeoc", "cisa"}\n'
        ")",
        "_EXACT_ONLY_KEYWORDS = frozenset()",
    ),
    (
        "exact-only entry that is not a keyword",
        "a dead entry reads as protection and provides none",
        '    {"sec", "seo", "ftc", "csf", "gaap", "xbrl", "eeoc", "cisa"}',
        '    {"sec", "seo", "ftc", "csf", "gaap", "xbrl", "eeoc", "cisa", "phi"}',
    ),
    (
        "privacy vocabulary removed",
        "the Phase 5 gap: ordinary privacy questions retrieve no legal evidence",
        '        "privacy",\n        "personal information",',
        '        "personal information",',
    ),
    (
        "statutory removed, relying on statute",
        '"statute" + suffix does not produce "statutory"; this was the real miss',
        '        "statutory",\n',
        "",
    ),
    (
        "regulator removed, relying on regulation",
        '"regulation" does not cover "regulator" or "regulatory"',
        '        "regulator",\n',
        "",
    ),
    (
        "compliance markers back to naked substring",
        "fixing departments but not markers leaves half the router by accident",
        "    if any(m.search(lower) for m in _COMPLIANCE_MATCHERS):",
        "    if any(m in lower for m in _COMPLIANCE_MARKERS):",
    ),
    (
        "matchers hand-written instead of derived",
        "adding a keyword silently stops having any effect",
        "_DEPT_MATCHERS: dict[str, tuple[re.Pattern[str], ...]] = {\n"
        "    dept: tuple(_compile_keyword(k) for k in keys)\n"
        "    for dept, keys in _DEPT_KEYWORDS.items()\n"
        "}",
        "_DEPT_MATCHERS: dict[str, tuple[re.Pattern[str], ...]] = {\n"
        "    dept: tuple(_compile_keyword(k) for k in keys[:3])\n"
        "    for dept, keys in _DEPT_KEYWORDS.items()\n"
        "}",
    ),
]


def _run_tests() -> bool:
    """True when the suite passes."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "--no-header", "-p", "no:cacheprovider"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    original = ROUTER.read_text(encoding="utf-8")

    if not _run_tests():
        print("BASELINE FAILS -- fix the suite before mutating.")
        return 2
    print("baseline: PASS\n")

    caught = 0
    escaped: list[str] = []
    try:
        for i, (name, why, old, new) in enumerate(MUTATIONS, 1):
            if old not in original:
                print(f"{i:2}. SKIP (anchor not found) {name}")
                escaped.append(f"{name} [anchor missing]")
                continue
            ROUTER.write_text(original.replace(old, new, 1), encoding="utf-8")
            failed = not _run_tests()
            if failed:
                caught += 1
                print(f"{i:2}. caught   {name}")
            else:
                escaped.append(name)
                print(f"{i:2}. ESCAPED  {name}")
            print(f"     {why}")
    finally:
        ROUTER.write_text(original, encoding="utf-8")

    print()
    print(f"{caught}/{len(MUTATIONS)} caught")
    if escaped:
        print("escaped:")
        for e in escaped:
            print(f"   {e}")
    if not _run_tests():
        print("WARNING: suite red after restore -- the file may not be clean.")
        return 2
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
