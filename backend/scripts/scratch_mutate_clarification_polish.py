"""Mutation proof for site 11's regression tests.

Same discipline as sites 7-10. This site degraded to a legitimate-looking
template question, so the suite has to distinguish "the model polished it" from
"the template happened to be fine", not merely assert a question came back.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SRC = BACKEND / "app" / "services" / "clarification_engine.py"
TESTS = "tests/services/test_clarification_polish_reaches_model.py"

MUTATIONS: list[tuple[str, str, str]] = [
    (
        "the original dormant call is restored (the actual bug)",
        "            response = await get_model_router().complete(",
        "            response = await get_model_router(self.settings).complete(",
    ),
    (
        "the polished question is discarded and the template always wins",
        "            return polished or question",
        "            return question",
    ),
    (
        "the draft stops reaching the prompt, so the rewrite is unanchored",
        '                    f"Draft: {draft}"',
        '                    ""',
    ),
    (
        "empty model output is returned instead of falling back to the template",
        "            return text if text else None",
        "            return text",
    ),
    (
        "high_risk_confirmation copy is now rewritten by a model",
        '        if len(question) > 20 and trigger_type != "high_risk_confirmation":',
        "        if len(question) > 20:",
    ),
    (
        "the length gate is removed, so trivial questions pay for a model call",
        '        if len(question) > 20 and trigger_type != "high_risk_confirmation":',
        '        if trigger_type != "high_risk_confirmation":',
    ),
    (
        "graceful degradation removed — a provider outage now raises",
        '        except Exception as exc:  # noqa: BLE001\n'
        '            logger.warning("clarification polish skipped: %s", exc)\n'
        "            return None",
        "        except Exception:\n            raise",
    ),
    (
        "the model output is no longer stripped",
        '            text = (response.content or "").strip()',
        '            text = (response.content or "")',
    ),
    (
        "classification moves off the cheap tier",
        "                task_type=TaskType.CLASSIFICATION,\n"
        "                prompt=(\n"
        '                    "Rewrite as one natural clarifying question. No bullet lists.\\n\\n"',
        "                task_type=TaskType.REASONING,\n"
        "                prompt=(\n"
        '                    "Rewrite as one natural clarifying question. No bullet lists.\\n\\n"',
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
                print(f"  SKIP     {label} — anchor not found")
                results.append((label, "skipped"))
                continue
            SRC.write_text(original.replace(find, replace, 1), encoding="utf-8")
            caught = not run_tests()
            print(f"  {'caught  ' if caught else 'SURVIVED'} {label}")
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
