"""Mutation test: are the HubSpot search tests actually load-bearing?

Three green suites accompanied three live failures earlier in this program, so a
passing test proves nothing on its own. Each mutation below reintroduces a real
variant of the original defect; the suite must go red for every one.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "app" / "services" / "tool_service.py"
TESTS = "tests/services/test_hubspot_search_honors_advertised_schema.py"
TESTS_ERR = "tests/services/test_hubspot_error_classification.py"

MUTATIONS = [
    (
        "resolver ignores the advertised query param",
        """    for key in ("query", "q", "search", "search_term", "keyword"):
        raw = params.get(key)
        if isinstance(raw, str) and raw.strip():
            return _hubspot_text_filter_groups(object_type, raw.strip())
    return None""",
        """    return None""",
    ),
    (
        "deals search dead-ends on a criteria-less call (the original bug)",
        """        if filter_groups is None:
            data = list_deals(token, properties=params.get("properties"), limit=limit)
        else:
            data = search_deals(""",
        """        if filter_groups is None:
            raise ToolValidationError("hubspot.deals.search requires filter_groups array")
        else:
            data = search_deals(""",
    ),
    (
        "resolver lets query override an explicit filter",
        """    filter_groups = params.get("filter_groups") or params.get("filterGroups")
    if isinstance(filter_groups, list) and filter_groups:
        return filter_groups
    for key in ("query",""",
        """    filter_groups = params.get("filter_groups") or params.get("filterGroups")
    if False:
        return filter_groups
    for key in ("query",""",
    ),
    (
        "contacts free-text collapses to a single property",
        """    props = _HUBSPOT_TEXT_SEARCH_PROPERTIES.get(object_type) or ("name",)""",
        """    props = (_HUBSPOT_TEXT_SEARCH_PROPERTIES.get(object_type) or ("name",))[:1]""",
    ),
    (
        "every non-auth failure is a validation error again (the mislabel bug)",
        """    if status is not None and 400 <= status < 500:
        return ToolValidationError(str(exc))""",
        """    return ToolValidationError(str(exc))
    if False:
        return ToolValidationError(str(exc))""",
    ),
    (
        "timeouts lose their dedicated code",
        """    if status is None and ("timeout" in text or "timed out" in text):
        return ToolError(str(exc), code="connector_timeout")""",
        """    if False:
        return ToolError(str(exc), code="connector_timeout")""",
    ),
    (
        "real 4xx client errors stop being validation errors",
        """    if status is not None and 400 <= status < 500:""",
        """    if status is not None and 400 <= status < 401:""",
    ),
]


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", TESTS, TESTS_ERR, "-q", "--no-header", "-x"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, (proc.stdout or "")[-400:]


def main() -> int:
    original = TOOL.read_text(encoding="utf-8")

    ok, tail = run_tests()
    print(f"baseline (unmutated): {'PASS' if ok else 'FAIL'}")
    if not ok:
        print(tail)
        print("baseline must pass before mutating")
        return 1

    results = []
    try:
        for label, find, replace in MUTATIONS:
            if find not in original:
                print(f"\n[{label}] SKIP — anchor not found, mutation not applied")
                results.append((label, None))
                continue
            TOOL.write_text(original.replace(find, replace, 1), encoding="utf-8")
            ok, tail = run_tests()
            caught = not ok
            print(f"\n[{label}]")
            print(f"  suite {'FAILED (mutation caught)' if caught else 'PASSED (MUTATION SURVIVED)'}")
            if not caught:
                print("  >>> the test is not load-bearing for this behavior")
            results.append((label, caught))
            TOOL.write_text(original, encoding="utf-8")
    finally:
        TOOL.write_text(original, encoding="utf-8")

    ok, _ = run_tests()
    print(f"\nrestored baseline: {'PASS' if ok else 'FAIL'}")

    print("\n=== SUMMARY ===")
    survived = [l for l, c in results if c is False]
    skipped = [l for l, c in results if c is None]
    for label, caught in results:
        state = "caught" if caught else ("SURVIVED" if caught is False else "skipped")
        print(f"  {state:9} {label}")
    if survived:
        print(f"\n{len(survived)} mutation(s) survived — tests are not sufficient proof")
        return 1
    if skipped:
        print(f"\n{len(skipped)} mutation(s) could not be applied")
        return 1
    print(f"\nall {len(results)} mutations caught — tests are load-bearing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
