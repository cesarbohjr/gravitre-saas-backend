"""Mutation proof for site 7's regression tests.

Especially warranted here: the PRE-EXISTING test for this function passes with
the bug present (see scratch_prove_existing_rewriter_test_blind.py). A green
suite has already failed to protect this exact code once, so the replacement
suite has to be shown load-bearing rather than assumed to be.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SRC = BACKEND / "app" / "services" / "query_rewriter.py"
TESTS = "tests/services/test_query_rewriter_reaches_model.py"

MUTATIONS: list[tuple[str, str, str]] = [
    (
        "the original dormant call is restored (the actual bug)",
        "        router = get_model_router()",
        "        router = get_model_router(settings)",
    ),
    (
        "the rewritten query is discarded and the original returned",
        "            if refined and refined.lower() != original.lower():",
        "            if False:",
    ),
    (
        "conversation history stops being sent, so pronouns cannot resolve",
        "        f\"Conversation:\\n{history_block}\\n\\n\"",
        "        \"\"",
    ),
    (
        "the length cap is removed",
        "refined[:2000]",
        "refined",
    ),
    (
        "the model is consulted even with no usable history (cost leak)",
        "    if not recent_lines:\n"
        "        return {\"original_query\": original, \"refined_query\": original, \"model_ran\": False}",
        "    pass",
    ),
    (
        "an empty query now reaches the model",
        "    if not original:\n"
        "        return {\"original_query\": \"\", \"refined_query\": \"\", \"model_ran\": False}",
        "    pass",
    ),
    (
        "classification silently moves off the cheap intent tier",
        "            task_type=TaskType.INTENT_DETECTION,",
        "            task_type=TaskType.REASONING,",
    ),
    (
        "org_id stops being propagated for attribution",
        "            org_id=org_id,",
        "            org_id=None,",
    ),
    (
        "model_ran always reports True, so the audit event cannot reveal dormancy",
        "    model_ran = False\n",
        "    model_ran = True\n",
    ),
    (
        "model_ran is set before the call completes, so a failure reads as a run",
        "        router = get_model_router()\n"
        "        response = await router.complete(",
        "        model_ran = True\n"
        "        router = get_model_router()\n"
        "        response = await router.complete(",
    ),
    (
        "graceful degradation removed — a provider outage now raises",
        "    except Exception as exc:  # noqa: BLE001\n"
        "        logger.warning(\"query rewrite skipped org_id=%s error=%s\", org_id, exc)",
        "    except Exception:\n"
        "        raise",
    ),
]


def run_tests() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "-x", "--no-header"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def main() -> int:
    original = SRC.read_text(encoding="utf-8")

    print("baseline (fix in place):", end=" ", flush=True)
    if not run_tests():
        print("FAIL — baseline is already red, cannot mutation-test")
        return 1
    print("PASS")

    results = []
    try:
        for label, find, replace in MUTATIONS:
            if find not in original:
                print(f"  SKIP  {label} — anchor not found")
                results.append((label, "skipped"))
                continue
            SRC.write_text(original.replace(find, replace, 1), encoding="utf-8")
            caught = not run_tests()
            print(f"  {'caught ' if caught else 'SURVIVED'} {label}")
            results.append((label, "caught" if caught else "survived"))
            SRC.write_text(original, encoding="utf-8")
    finally:
        SRC.write_text(original, encoding="utf-8")

    print("\nrestored baseline:", end=" ", flush=True)
    print("PASS" if run_tests() else "FAIL")

    print("\n=== SUMMARY ===")
    for label, outcome in results:
        print(f"  {outcome:9s} {label}")

    survived = [r for r in results if r[1] != "caught"]
    if survived:
        print(f"\n{len(survived)} mutation(s) not caught — tests are not load-bearing")
        return 1
    print(f"\nall {len(results)} mutations caught — tests are load-bearing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
