#!/usr/bin/env python3
"""Mutation proof for the three-way classification and the loop's actions.

Phase 2 asks specifically for this: disable the retry trigger and confirm the
tests genuinely fail. The mutations go further, because the risky part of this
change is not the retry (which already existed and was already bounded) but the
two NEW actions -- discarding evidence and refining it. Both destroy material,
so a silent regression in either is worse than the original binary verdict.

The single most important mutation is `discard_rows_but_keep_sections`: it is a
change that keeps every audit count correct while the model goes on reading the
evidence that was supposedly thrown away.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
CTX = BACKEND / "app" / "services" / "unified_turn_knowledge_context.py"
SUFF = BACKEND / "app" / "services" / "evidence_sufficiency_service.py"
TESTS = "tests/services/test_crag_three_way_loop.py tests/services/test_evidence_sufficiency_loop.py"

sys.stdout.reconfigure(encoding="utf-8")

# (label, target file, find, replace)
MUTATIONS: list[tuple[str, Path, str, str]] = [
    (
        "disable the retry trigger entirely (Phase 2's required mutation)",
        CTX,
        "while not verdict.sufficient and loop_meta[\"additional_rounds_used\"] < max_rounds:",
        "while False:",
    ),
    (
        "unbound the loop",
        CTX,
        "while not verdict.sufficient and loop_meta[\"additional_rounds_used\"] < max_rounds:",
        "while not verdict.sufficient and loop_meta[\"additional_rounds_used\"] < 9999:",
    ),
    (
        "discard the rows but leave the rendered sections in the prompt",
        CTX,
        "                rag_source_rows = []\n                evidence_sections.clear()",
        "                rag_source_rows = []",
    ),
    (
        "never discard (treat INCORRECT like AMBIGUOUS)",
        CTX,
        "            if verdict.should_discard_evidence:",
        "            if False:",
    ),
    (
        "let refinement empty the evidence set",
        CTX,
        "            if kept and len(kept) < len(candidates):",
        "            if len(kept) <= len(candidates):",
    ),
    (
        "refine on any stance, not just CORRECT",
        CTX,
        "        if verdict.stance == STANCE_CORRECT and verdict.keep_indices:",
        "        if verdict.keep_indices:",
    ),
    (
        "make stance advisory instead of authoritative",
        SUFF,
        "        self.sufficient = self.stance == STANCE_CORRECT",
        "        pass",
    ),
    (
        "default a legacy false bool to INCORRECT (destructive default)",
        SUFF,
        "                self.stance = STANCE_CORRECT if self.sufficient else STANCE_AMBIGUOUS",
        "                self.stance = STANCE_CORRECT if self.sufficient else STANCE_INCORRECT",
    ),
    (
        "let an unrecognised stance certify the evidence",
        SUFF,
        "            logger.warning(\"sufficiency_stance_unrecognized value=%s\", candidate[:40])\n            return STANCE_AMBIGUOUS, True",
        "            return STANCE_CORRECT, True",
    ),
    (
        "stop flagging inferred stances",
        SUFF,
        "            self.stance_inferred = True\n            if self.assessor in UNAVAILABLE_ASSESSORS:",
        "            if self.assessor in UNAVAILABLE_ASSESSORS:",
    ),
    (
        "treat a broken assessor as a reasoned shortfall",
        SUFF,
        "            stance=STANCE_UNKNOWN,\n        )",
        "            stance=STANCE_INCORRECT,\n        )",
    ),
    (
        "drop the stance fields from the audit payload",
        CTX,
        '        "finalStance": loop_meta.get("final_stance"),',
        "",
    ),
    (
        "misalign the refinement index basis",
        CTX,
        "            candidates = substantive_rows(rag_source_rows)",
        "            candidates = list(rag_source_rows)",
    ),
    (
        "invite a guess when all evidence was discarded",
        CTX,
        "            if verdict.should_discard_evidence and not rag_source_rows:",
        "            if False:",
    ),
]


def run_tests() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS.split(), "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8") for p in (CTX, SUFF)}
    backups = {}
    for p in originals:
        b = p.with_suffix(".py.mutbak")
        shutil.copy2(p, b)
        backups[p] = b

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_tests():
        print("FAIL - suite is red before mutating; fix that first")
        for p, b in backups.items():
            shutil.move(b, p)
        return 2
    print("green")
    print()

    caught = 0
    escaped: list[str] = []
    try:
        for label, target, find, replace in MUTATIONS:
            src = originals[target]
            if find not in src:
                print(f"  [SKIP] {label} - anchor not found, mutation is stale")
                escaped.append(f"{label} (stale anchor)")
                continue
            target.write_text(src.replace(find, replace, 1), encoding="utf-8")
            red = not run_tests()
            target.write_text(src, encoding="utf-8")
            print(f"  [{'caught' if red else 'ESCAPED'}] {label}")
            if red:
                caught += 1
            else:
                escaped.append(label)
    finally:
        for p, b in backups.items():
            shutil.move(b, p)

    print()
    print(f"  {caught}/{len(MUTATIONS)} mutations caught")
    for item in escaped:
        print(f"  ESCAPED: {item}")
    print(f"  restored; suite green again: {run_tests()}")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
