#!/usr/bin/env python3
"""Mutation proof for the Knowledge Fabric keyword-arm guards.

A guard that cannot fail is not a guard. Each mutation below reintroduces one of
the real defects that shipped, and the suite must go red for every one. The
originals lived in production behind 71 green tests, so "the tests pass" is
explicitly not the bar here.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
TARGET = BACKEND / "app" / "knowledge_fabric" / "retrieval.py"
TESTS = "tests/knowledge_fabric/test_fabric_fts_arm.py"

sys.stdout.reconfigure(encoding="utf-8")

MUTATIONS: list[tuple[str, str, str]] = [
    (
        "restore the config= kwarg (the original TypeError)",
        '.text_search("content_tsv", fts_query, FTS_OPTIONS)',
        '.text_search("content_tsv", fts_query, config="english")',
    ),
    (
        "use the near-miss option key 'websearch'",
        'FTS_OPTIONS = {"type": "web_search", "config": "english"}',
        'FTS_OPTIONS = {"type": "websearch", "config": "english"}',
    ),
    (
        "drop the cause back into extra= and downgrade to info",
        'logger.warning(\n                "knowledge_fabric.fts_unavailable error=%s: %s",\n'
        "                type(exc).__name__,\n                str(exc)[:200],\n            )",
        'logger.info("knowledge_fabric.fts_unavailable", extra={"error": str(exc)[:160]})',
    ),
    (
        "AND the whole sentence instead of ORing content terms",
        'return " OR ".join(f\'"{term}"\' for term in seen)',
        'return " ".join(seen)',
    ),
    (
        "collapse no_terms into the ok state",
        'FTS_NO_TERMS = "no_terms"',
        'FTS_NO_TERMS = "ok"',
    ),
    (
        "strip retrieval_health from the main return",
        '"retrieval_health": health,',
        "",
    ),
]


def run_tests() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    backup = TARGET.with_suffix(".py.mutbak")
    shutil.copy2(TARGET, backup)
    original = TARGET.read_text(encoding="utf-8")

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_tests():
        print("FAIL - suite is red before mutating; fix that first")
        shutil.move(backup, TARGET)
        return 2
    print("green")
    print()

    caught = 0
    escaped: list[str] = []
    try:
        for label, find, replace in MUTATIONS:
            if find not in original:
                print(f"  [SKIP] {label} - anchor not found, mutation is stale")
                escaped.append(f"{label} (stale anchor)")
                continue
            TARGET.write_text(original.replace(find, replace, 1), encoding="utf-8")
            red = not run_tests()
            print(f"  [{'caught' if red else 'ESCAPED'}] {label}")
            if red:
                caught += 1
            else:
                escaped.append(label)
    finally:
        shutil.move(backup, TARGET)

    print()
    print(f"  {caught}/{len(MUTATIONS)} mutations caught")
    for item in escaped:
        print(f"  ESCAPED: {item}")
    print(f"  restored {TARGET.name}; suite green again: {run_tests()}")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
