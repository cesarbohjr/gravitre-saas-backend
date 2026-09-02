#!/usr/bin/env python3
"""Mutation proof for the evidence.sufficiency.assessed audit instrument.

A green suite proves the tests pass, not that they would notice the bug coming
back. Each mutation below reintroduces a regression this program has actually
shipped before, and the run fails if any of them slips through.

    python scripts/mutate_sufficiency_audit.py

Restores every file in a finally block, and verifies the tree is clean at the
end.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend"
CTX = BACKEND / "app" / "services" / "unified_turn_knowledge_context.py"
SUFF = BACKEND / "app" / "services" / "evidence_sufficiency_service.py"
TURN = BACKEND / "app" / "services" / "unified_turn_reasoning_service.py"

TESTS = [
    "tests/services/test_sufficiency_audit_action.py",
    "tests/services/test_evidence_sufficiency_loop.py",
    "tests/test_audit_instruments_have_real_actor.py",
]


@dataclass
class Mutation:
    name: str
    path: Path
    old: str
    new: str
    why: str


MUTATIONS = [
    Mutation(
        name="no audit event at all",
        path=CTX,
        old="        await asyncio.to_thread(\n            _emit_sufficiency_audit,",
        new="        _ = (\n            _emit_sufficiency_audit,",
        why="the original gap: a live gate with no queryable action",
    ),
    Mutation(
        name="actor guard removed (silent drop)",
        path=CTX,
        old="""    if not (actor_id and is_uuid(actor_id)) or not (
        conversation_id and is_uuid(conversation_id)
    ):""",
        new="    if False:",
        why="actor_id=None reaches write_audit_event and the insert vanishes silently",
    ),
    Mutation(
        name="assessorRan compared against a literal",
        path=CTX,
        old='"assessorRan": any(a in MODEL_ASSESSORS for a in assessors),',
        new='"assessorRan": any(a == "model" for a in assessors),',
        why="the exact grounding-validator bug: a literal that never matches",
    ),
    Mutation(
        name="assessorRan counts deterministic as a model judgement",
        path=CTX,
        old='"assessorRan": any(a in MODEL_ASSESSORS for a in assessors),',
        new='"assessorRan": bool(assessors),',
        why="a structural short-circuit reported as though a model reasoned",
    ),
    Mutation(
        name="fail-closed no longer announced",
        path=CTX,
        old='"assessorUnavailable": any(a in UNAVAILABLE_ASSESSORS for a in assessors),',
        new='"assessorUnavailable": False,',
        why="an unjudged turn becomes indistinguishable from a real shortfall",
    ),
    Mutation(
        name="audit write no longer guarded",
        path=CTX,
        old="""    try:
        from app.workflows.audit import write_audit_event

        write_audit_event(""",
        new="""    if True:
        from app.workflows.audit import write_audit_event

        write_audit_event(""",
        why="an audit outage would take the whole turn down with it",
    ),
    Mutation(
        name="emitted on skipped turns too",
        path=CTX,
        old='    if not loop_enabled or bar.name == BAR_CASUAL or max_rounds == 0:',
        new='    if False:',
        why="a DB write added to the conversational fast path",
    ),
    Mutation(
        name="call site stops threading the actor",
        path=TURN,
        old="            actor_id=user_id,\n            conversation_id=conversation_id,",
        new="            actor_id=None,\n            conversation_id=None,",
        why="'one layer too low': emitter correct, caller supplies nothing",
    ),
    Mutation(
        name="assessor constant drifts from its value",
        path=SUFF,
        old='ASSESSOR_LLM = "llm"',
        new='ASSESSOR_LLM = "llm_v2"',
        why="a rename that would silently zero assessorRan if compared loosely",
    ),
]


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "-p", "no:randomly", "-x"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, (proc.stdout or "")[-400:]


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8") for p in {CTX, SUFF, TURN}}

    ok, tail = run_tests()
    if not ok:
        print("BASELINE IS RED -- fix before mutating\n" + tail)
        return 1
    print("baseline: green\n")

    caught, missed = 0, []
    try:
        for mut in MUTATIONS:
            src = originals[mut.path]
            if mut.old not in src:
                print(f"  SKIP  {mut.name}: anchor not found (code moved?)")
                missed.append(f"{mut.name} (anchor missing)")
                continue
            mut.path.write_text(src.replace(mut.old, mut.new, 1), encoding="utf-8")
            passed, _ = run_tests()
            mut.path.write_text(src, encoding="utf-8")
            if passed:
                print(f"  MISSED  {mut.name}\n            ({mut.why})")
                missed.append(mut.name)
            else:
                print(f"  caught  {mut.name}")
                caught += 1
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")

    print(f"\n{caught}/{len(MUTATIONS)} mutations caught")
    if missed:
        print("MISSED:")
        for m in missed:
            print(f"  - {m}")

    ok, tail = run_tests()
    print(f"restored baseline: {'green' if ok else 'RED -- ' + tail}")
    return 0 if (not missed and ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
