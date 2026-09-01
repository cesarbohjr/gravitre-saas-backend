"""Mutation-prove the sites 9/10 guards.

This program has repeatedly found green suites that passed *because* their mocks
encoded the same wrong assumption as the code. A test that cannot fail when the
fix is removed is not evidence. Each mutation below deliberately breaks the fix
or a behaviour the tests claim to pin; every one must turn the suite red.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CUS = BACKEND / "app" / "services" / "contextual_understanding_service.py"
DIS = BACKEND / "app" / "services" / "domain_intelligence_service.py"
TESTS = "tests/services/test_understanding_and_domain_reach_model.py"

MUTATIONS: list[tuple[str, Path, str, str]] = [
    (
        "site 9: restore the dormant arity",
        CUS,
        "await get_model_router().complete(",
        "await get_model_router(self.settings).complete(",
    ),
    (
        "site 10: restore the dormant arity",
        DIS,
        "await get_model_router().complete(",
        "await get_model_router(self.settings).complete(",
    ),
    (
        "site 9: swallow the parsed result and return the default",
        CUS,
        "            parsed = json.loads(clean)",
        "            parsed = None",
    ),
    (
        "site 10: ignore the model and always keep the rule result",
        DIS,
        "            parsed = json.loads(clean)",
        "            return rule_result",
    ),
    (
        "site 9: widen the rule gate so the model is never consulted",
        CUS,
        "        return len(text.split()) <= 12",
        "        return True",
    ),
    (
        "site 10: drop the low-confidence tier entirely",
        DIS,
        "        llm_result = await self._classify_by_llm(message, org_hints, org_boosted)",
        "        llm_result = {}",
    ),
]


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, "-q", "--no-header", "-x"],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
        timeout=900,
    )
    return proc.returncode == 0, (proc.stdout or "")[-400:]


def main() -> int:
    ok, out = run_tests()
    if not ok:
        print("BASELINE IS RED — fix the suite before mutating\n" + out)
        return 1
    print("baseline: green\n")

    caught = 0
    for name, path, old, new in MUTATIONS:
        original = path.read_text(encoding="utf-8")
        if old not in original:
            print(f"  SKIP (anchor not found): {name}")
            continue
        path.write_text(original.replace(old, new, 1), encoding="utf-8")
        try:
            passed, tail = run_tests()
        finally:
            path.write_text(original, encoding="utf-8")
        if passed:
            print(f"  SURVIVED (test is blind): {name}")
        else:
            caught += 1
            print(f"  caught: {name}")

    total = sum(1 for _, p, o, _ in MUTATIONS if o in p.read_text(encoding="utf-8"))
    print(f"\n{caught}/{total} mutations caught")

    ok, _ = run_tests()
    print(f"restored baseline green: {ok}")
    return 0 if caught == total and ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
