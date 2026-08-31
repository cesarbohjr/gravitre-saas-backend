"""Mutation-test the evidence-sufficiency replan loop guards (2026-08-31).

This program has repeatedly found suites that passed *because* they encoded the
same wrong assumption as the code. So each guard here is checked the only way
that means anything: break the behaviour in the source, and require the named
test to fail. A mutation that stays green marks a test that was never
load-bearing.

The mutations restore the exact pre-fix behaviours this work exists to prevent:
unbounded iteration, a loop that ignores the fast path, escalation that re-reads
a source it already read, a contradiction resolver that always picks a winner,
and a silent shortfall.

Source files are restored in a finally block.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
CTX = BACKEND / "app" / "services" / "unified_turn_knowledge_context.py"
SUFF = BACKEND / "app" / "services" / "evidence_sufficiency_service.py"
CONTRA = BACKEND / "app" / "services" / "evidence_contradiction_service.py"

LOOP_TESTS = "tests/services/test_evidence_sufficiency_loop.py"
CONTRA_TESTS = "tests/services/test_evidence_contradiction.py"

sys.stdout.reconfigure(encoding="utf-8")


def run(path: str, test: str) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", f"{path}::{test}", "-q"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    return proc.returncode, tail[-1] if tail else "(no output)"


def _sub(path: Path, old: str, new: str, label: str) -> str:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"mutation anchor not found in {path.name}: {old[:70]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    return label


# --- mutations -------------------------------------------------------------


def remove_hard_bound() -> str:
    return _sub(
        CTX,
        "while not verdict.sufficient and loop_meta[\"additional_rounds_used\"] < max_rounds:",
        "while not verdict.sufficient and loop_meta[\"additional_rounds_used\"] < 9999:",
        "removed the iteration cap (while ... < 9999)",
    )


def remove_max_rounds_clamp() -> str:
    return _sub(
        CTX,
        "return max(0, min(MAX_ADDITIONAL_ROUNDS_CEILING, value))",
        "return max(0, value)",
        "removed the ceiling clamp on evidence_sufficiency_max_rounds",
    )


def ignore_fast_path() -> str:
    return _sub(
        SUFF,
        'if (reasoning_depth or "full").strip().lower() == "conversational":',
        'if False:',
        "made the bar ignore conversational reasoning_depth (fast path pays for the loop)",
    )


def escalate_to_an_already_tried_source() -> str:
    return _sub(
        CTX,
        "next_source = next((s for s in ESCALATION_ORDER if s not in tried), None)",
        "next_source = ESCALATION_ORDER[0]",
        "escalation re-picks the first source even when already tried",
    )


def silence_the_shortfall() -> str:
    return _sub(
        CTX,
        "        if not verdict.sufficient:\n",
        "        if False:\n",
        "removed the honest shortfall warning from the prompt",
    )


def flatten_the_regulatory_bar() -> str:
    return _sub(
        SUFF,
        "            name=BAR_REGULATORY,\n            min_sources=2,\n            require_citable_source=True,\n            require_freshness_signal=True,",
        "            name=BAR_REGULATORY,\n            min_sources=1,\n            require_citable_source=False,\n            require_freshness_signal=False,",
        "flattened the regulatory bar down to the business bar",
    )


def always_pick_a_winner() -> str:
    return _sub(
        CONTRA,
        '    contradiction.resolution = "unresolved"',
        '    contradiction.resolution = "resolved_authority"\n    contradiction.winner_index = claims[0].get("index")',
        "contradiction resolver always picks claims[0] instead of reporting unresolved",
    )


def revert_authority_scale_fix() -> str:
    """The exact bug real corpus data exposed: a 0..100 threshold on 0..1 data."""
    return _sub(
        CONTRA,
        "    return score / 100.0 if score > 1.0 else score",
        "    return score",
        "removed 0..1 / 0..100 authority normalization (rung dies on real data)",
    )


def restore_freshness_dead_end() -> str:
    """The dead end live traffic exposed: undated evidence vetoed before reasoning."""
    return _sub(
        SUFF,
        "    freshness_missing = bar.require_freshness_signal and not _has_freshness_signal(\n        substantive\n    )",
        "    freshness_missing = bar.require_freshness_signal and not _has_freshness_signal(\n        substantive\n    )\n    if freshness_missing:\n        return SufficiencyVerdict(\n            sufficient=False,\n            bar=bar,\n            assessor='deterministic',\n            reason='no freshness signal',\n            gaps=['no_freshness_signal'],\n            confidence=None,\n        )",
        "restored the hard freshness veto (undated web evidence never reaches the assessor)",
    )


def always_report_process() -> str:
    return _sub(
        SUFF,
        "    if rounds == 0 and not fell_short and conflict_count == 0:\n        return None",
        "    if False:\n        return None",
        "process summary emitted on every turn (verbosity on clean single-pass answers)",
    )


MUTATIONS = [
    (CTX, LOOP_TESTS, "test_the_cap_binds_even_when_more_sources_remain_untried", remove_hard_bound),
    (CTX, LOOP_TESTS, "test_max_rounds_is_clamped_to_the_ceiling", remove_max_rounds_clamp),
    (SUFF, LOOP_TESTS, "test_conversational_turn_pays_nothing_for_the_loop", ignore_fast_path),
    (CTX, LOOP_TESTS, "test_insufficient_evidence_escalates_to_a_source_not_yet_tried", escalate_to_an_already_tried_source),
    (CTX, LOOP_TESTS, "test_iteration_is_hard_bounded_and_the_shortfall_is_stated", silence_the_shortfall),
    (SUFF, LOOP_TESTS, "test_regulatory_questions_get_a_higher_bar_than_business_questions", flatten_the_regulatory_bar),
    (SUFF, LOOP_TESTS, "test_undated_evidence_is_not_a_dead_end", restore_freshness_dead_end),
    (CONTRA, CONTRA_TESTS, "test_unresolved_conflict_is_surfaced_with_both_claims", always_pick_a_winner),
    (CONTRA, CONTRA_TESTS, "test_authority_works_on_the_scale_the_real_corpus_actually_uses", revert_authority_scale_fix),
    (SUFF, LOOP_TESTS, "test_clean_single_pass_produces_no_process_noise", always_report_process),
]


def main() -> int:
    originals = {p: p.read_text(encoding="utf-8") for p in (CTX, SUFF, CONTRA)}
    results = []
    try:
        for target, test_path, test, mutate in MUTATIONS:
            for path, text in originals.items():
                path.write_text(text, encoding="utf-8")
            description = mutate()
            code, last = run(test_path, test)
            results.append((target.name, test, description, code, last))
    finally:
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")

    all_caught = True
    for filename, test, description, code, last in results:
        caught = code != 0
        all_caught &= caught
        print(f"{'CAUGHT ' if caught else 'MISSED '} {test}")
        print(f"           file    : {filename}")
        print(f"           mutation: {description}")
        print(f"           pytest  : {last}")
        print()

    print("--- restored; full suites must pass again ---")
    clean = True
    for path in (LOOP_TESTS, CONTRA_TESTS):
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", path, "-q"],
            cwd=BACKEND,
            capture_output=True,
            text=True,
        )
        tail = (proc.stdout + proc.stderr).strip().splitlines()
        print(f"{'PASS' if proc.returncode == 0 else 'FAIL'} {path}: {tail[-1] if tail else ''}")
        clean &= proc.returncode == 0

    print(f"\nall mutations caught: {all_caught}")
    print(f"restored suites green: {clean}")
    return 0 if all_caught and clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
