"""Mutation proof for site 6's regression tests.

Green tests are not evidence; this program has repeatedly found tests that
passed for the wrong reason. Each mutation below is a real, plausible way the
fix could be undone. Every one must turn the suite red.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SRC = BACKEND / "app" / "services" / "conversation_turn_controller.py"
TESTS = "tests/services/test_pending_plan_intent_honors_model.py"

MUTATIONS: list[tuple[str, str, str]] = [
    (
        "the original dormant call is restored (the actual bug)",
        "response = await get_model_router().complete(",
        "response = await get_model_router(settings or get_settings()).complete(",
    ),
    (
        "modify-hint branch ignores the model and always returns modify",
        "            if model_intent in {\"continue\", \"modify\", \"cancel\"}:\n"
        "                return model_intent  # type: ignore[return-value]\n"
        "        return \"modify\"",
        "        return \"modify\"",
    ),
    (
        "cancel is dropped from the accepted labels, silently becoming modify",
        "            if model_intent in {\"continue\", \"modify\", \"cancel\"}:\n"
        "                return model_intent  # type: ignore[return-value]\n"
        "        return \"modify\"",
        "            if model_intent in {\"continue\", \"modify\"}:\n"
        "                return model_intent  # type: ignore[return-value]\n"
        "        return \"modify\"",
    ),
    (
        "the plan goal stops being sent, so 'that' has no referent",
        "            goal = str(current_plan.get(\"goal\") or current_plan.get(\"summary\") or \"\")[:300]",
        "            goal = \"\"",
    ),
    (
        "classification silently moves off the cheap fast tier",
        "            task_type=TaskType.CLASSIFICATION,\n"
        "            prompt=prompt,\n"
        "            system_prompt=(\n"
        "                'Respond as JSON: {\"intent\":\"continue|modify|cancel|unclear\",\"reason\":\"...\"}'\n"
        "            ),\n"
        "            temperature=0.0,\n"
        "            max_tokens=80,",
        "            task_type=TaskType.REASONING,\n"
        "            prompt=prompt,\n"
        "            system_prompt=(\n"
        "                'Respond as JSON: {\"intent\":\"continue|modify|cancel|unclear\",\"reason\":\"...\"}'\n"
        "            ),\n"
        "            temperature=0.7,\n"
        "            max_tokens=800,",
    ),
    (
        "the model is consulted for unambiguous replies too (cost/latency leak)",
        "    if is_clear_pending_cancel_intent(text):\n"
        "        return \"cancel\"\n"
        "    if CONFIRM_PATTERN.match(text) or text.lower() in {\"yes\", \"y\", \"ok\", \"okay\", \"confirm\"}:\n"
        "        return \"continue\"",
        "    pass",
    ),
    (
        "graceful degradation removed — a provider outage now raises",
        "    except Exception as exc:  # noqa: BLE001\n"
        "        logger.warning(\"pending plan intent model skipped: %s\", exc)\n"
        "    return \"unclear\"",
        "    except Exception:\n"
        "        raise\n"
        "    return \"unclear\"",
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
