#!/usr/bin/env python3
"""Mutation proof for the per-turn memory recall signal.

A green test suite proves nothing about the defect it was written for until the
defect is reintroduced and the suite goes red. Before
``test_unified_turn_attaches_narrowed_tools.py`` existed, the exact bug that
fired 109 times in production could be reintroduced with the whole suite green.

Each mutation below is a specific way the signal could silently stop working.
Every one must be CAUGHT.

Read-only against production. Restores every file on exit, including on failure.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
KERNEL = BACKEND / "app" / "services" / "cognitive_turn_kernel.py"
UNIFIED = BACKEND / "app" / "services" / "unified_turn_reasoning_service.py"
TESTS = "tests/services/test_memory_recall_signal.py"

# (label, file, find, replace)
MUTATIONS: list[tuple[str, Path, str, str]] = [
    (
        "recall never marks itself as having run",
        KERNEL,
        '        stats["ran"] = True',
        '        stats["ran"] = False',
    ),
    (
        "a store logs its failure at debug again (invisible in prod)",
        KERNEL,
        'logger.warning("cognitive_workspace_memory_recall_failed error=%s", exc)',
        'logger.debug("cognitive_workspace_memory_recall_failed error=%s", exc)',
    ),
    (
        "workspace store stops recording its outcome",
        KERNEL,
        '                _note_recall(stats, "workspace", count=got)',
        "                pass",
    ),
    (
        "rows are counted before cross-org isolation drops them",
        KERNEL,
        """                    if str(row.get("org_id") or "") != org_id:
                        continue""",
        """                    got += 0
                    if str(row.get("org_id") or "") != org_id:
                        got += 1
                        continue""",
    ),
    (
        "audit fires on every turn, including zero recalls",
        KERNEL,
        '    if not (signal.get("total") or signal.get("degraded")):\n        return',
        "    if False:\n        return",
    ),
    (
        "a degraded recall at zero rows is filed as found-nothing",
        KERNEL,
        '    if not (signal.get("total") or signal.get("degraded")):',
        '    if not signal.get("total"):',
    ),
    (
        "non-uuid actor is passed straight through to write_audit_event",
        KERNEL,
        "    if not (actor_id and is_uuid(actor_id)) or not (\n        conversation_id and is_uuid(conversation_id)\n    ):",
        "    if False:",
    ),
    (
        "unified turn stops merging the signal into its audit meta",
        UNIFIED,
        '                "memoryRecall": memory_recall_signal(cognitive_context),',
        "",
    ),
    (
        # Anchored on the surrounding lines, not a bare `else:`. A bare anchor
        # matched the first `else:` in a 2000-line module and mutated unrelated
        # code, which the suite correctly ignored and which read as a MISSED
        # mutation -- a broken instrument reporting a real guard as absent.
        "kernel meta merge is gated on a non-empty pack again",
        UNIFIED,
        """unified_turn_knowledge_meta = {**unified_turn_knowledge_meta, **kernel_meta}
            else:""",
        """unified_turn_knowledge_meta = {**unified_turn_knowledge_meta, **kernel_meta}
            elif mem or know or bias:""",
    ),
]


def run_tests() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    originals = {p: io.open(p, encoding="utf-8").read() for p in (KERNEL, UNIFIED)}

    def restore() -> None:
        for path, text in originals.items():
            io.open(path, "w", encoding="utf-8", newline="\n").write(text)

    try:
        if not run_tests():
            print("BASELINE RED -- fix the suite before trusting any mutation result")
            return 1
        print("baseline: GREEN\n")

        caught = 0
        for label, path, find, replace in MUTATIONS:
            text = originals[path]
            if find not in text:
                print(f"  SKIPPED (anchor gone) {label}")
                continue
            io.open(path, "w", encoding="utf-8", newline="\n").write(
                text.replace(find, replace, 1)
            )
            ok = run_tests()
            restore()
            verdict = "MISSED" if ok else "CAUGHT"
            if not ok:
                caught += 1
            print(f"  {verdict:7s} {label}")

        print(f"\n{caught}/{len(MUTATIONS)} caught")
        if not run_tests():
            print("RESTORE FAILED -- files left dirty, check git status")
            return 1
        print("restored: GREEN")
        return 0 if caught == len(MUTATIONS) else 1
    finally:
        restore()


if __name__ == "__main__":
    raise SystemExit(main())
