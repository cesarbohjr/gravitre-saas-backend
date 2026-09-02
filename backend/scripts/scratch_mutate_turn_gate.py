"""Mutation proof for site 8's regression tests.

Site 8 failed *closed*, which is the hardest variant to test honestly: the
degraded behaviour (task_shaped) is also a legitimate outcome, so a suite can
look green while asserting nothing about whether the model ever ran. These
mutations check the suite distinguishes "the model decided task_shaped" from
"the default decided it because the call was dormant".
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SRC = BACKEND / "app" / "services" / "conversational_turn_gate.py"
TESTS = "tests/services/test_turn_gate_reaches_model.py"

MUTATIONS: list[tuple[str, str, str]] = [
    (
        "the original dormant call is restored (the actual bug)",
        "        response = await get_model_router().complete(",
        "        response = await get_model_router(settings or get_settings()).complete(",
    ),
    (
        "used_model always reports True, hiding a dormant call from callers",
        "            used_model=True,\n        )\n    except Exception as exc:",
        "            used_model=False,\n        )\n    except Exception as exc:",
    ),
    (
        "the model's shape is discarded and everything becomes task_shaped",
        '        shape = str((parsed or {}).get("shape") or "task_shaped").lower().strip()',
        '        shape = "task_shaped"',
    ),
    (
        "mixed is no longer an accepted shape, killing the social-ack path",
        '        if shape not in {"conversational", "task_shaped", "mixed"}:',
        '        if shape not in {"conversational", "task_shaped"}:',
    ),
    (
        "the social/task split is dropped from the model result",
        '            social_portion=str((parsed or {}).get("social_portion") or "").strip(),',
        '            social_portion="",',
    ),
    (
        "raw JSON content is no longer parsed when parsed is absent",
        "                parsed = json.loads(response.content or \"{}\")",
        "                parsed = {}",
    ),
    (
        "the heuristic short-circuit is removed, so greetings pay for a model call",
        "    heuristic = heuristic_turn_shape(message)\n    if heuristic is not None:\n        return heuristic",
        "    heuristic = None",
    ),
    (
        "conversation summary stops reaching the prompt",
        '            f"Recent context: {(conversation_summary or \'\')[:400]}\\n"',
        '            ""',
    ),
    (
        "org_id stops being propagated for attribution",
        "            org_id=org_id,\n        )\n        parsed = response.parsed",
        "            org_id=None,\n        )\n        parsed = response.parsed",
    ),
    (
        "fail-closed becomes fail-open — real work can drop into chitchat",
        '            shape="task_shaped",\n            reason=f"model_unavailable:{exc}",',
        '            shape="conversational",\n            reason=f"model_unavailable:{exc}",',
    ),
    (
        "the task portion no longer falls back to the message",
        '            task_portion=str((parsed or {}).get("task_portion") or "").strip() or text,',
        '            task_portion=str((parsed or {}).get("task_portion") or "").strip(),',
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
