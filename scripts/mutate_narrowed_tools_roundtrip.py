"""Mutation test: do the new tests actually catch the two real regressions?

Each mutation reintroduces a defect that genuinely occurred (or that the fix
depends on not occurring). A mutation that survives means the corresponding
test is decorative, and that is reported rather than hidden.

Run from the repo root:  python scripts/mutate_narrowed_tools_roundtrip.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
NARROWED = BACKEND / "app" / "services" / "narrowed_tools.py"
UNIFIED = BACKEND / "app" / "services" / "unified_turn_reasoning_service.py"

TESTS = [
    "tests/services/test_narrowed_tools_survive_payload_conversion.py",
    "tests/services/test_non_openai_provider_tool_attach.py",
    "tests/services/test_unified_turn_attaches_narrowed_tools.py",
    "tests/services/test_g5_unnarrowed_tool_attach_guard.py",
    "tests/services/test_provider_tool_router.py",
    "tests/test_no_narrowed_tools_strips.py",
]

CONVERSION = '''                kwargs["tools"] = openai_tools_payload(
                    round_tools, where=f"unified_turn.round_{prog_round}"
                )'''

MUTATIONS: list[tuple[str, Path, str, str]] = [
    (
        "M1: as_openai_tools returns a plain list again (the design trap)",
        NARROWED,
        """        return NarrowedTools(
            [openai_tool_payload(t) for t in self],
            stats=self.stats,
            source=self.source,
        )""",
        "        return [openai_tool_payload(t) for t in self]",
    ),
    (
        "M2: attach site hand-rolls the conversion again (instance 2)",
        UNIFIED,
        CONVERSION,
        '                kwargs["tools"] = [openai_tool_payload(t) for t in round_tools]',
    ),
    (
        "M3: openai_tools_payload converts without checking first (laundering)",
        NARROWED,
        """    assert_tools_narrowed(tools, where=where)
    if isinstance(tools, NarrowedTools):
        return tools.as_openai_tools()""",
        """    if isinstance(tools, NarrowedTools):
        return tools.as_openai_tools()""",
    ),
    (
        "M6: strip before a preserver, killing its branch (instance 3, line 559)",
        UNIFIED,
        "    visible = _stable_tool_list(visible or [])",
        "    visible = _stable_tool_list(list(visible or []))",
    ),
    (
        # The faithful pre-65161f90 shape: no preserving branch at all, so
        # list() strips the marker on every tool-carrying turn. Mutating only
        # the `else` arm is NOT a faithful reproduction, because attach_tools is
        # always a NarrowedTools in practice and that arm never executes.
        "M4: preserving branch removed (instance 1, the actual 08-13 defect)",
        UNIFIED,
        """            elif isinstance(attach_tools, NarrowedTools):
                round_tools = attach_tools
            else:
                # attach_tools was asserted narrowed before this loop, so plain
                # list() here would strip proof that is already established.
                round_tools = mark_narrowed(
                    list(attach_tools or []),
                    stats=getattr(attach_tools, "stats", None),
                    source=str(getattr(attach_tools, "source", "") or "narrow_tools_for_turn"),
                )""",
        """            else:
                round_tools = list(attach_tools or [])""",
    ),
    (
        "M5: guard downgraded to a no-op (the invariant itself)",
        NARROWED,
        """    if getattr(tools, "gravitre_narrowed", False):
        return
    raise RuntimeError(""",
        """    if True:
        return
    raise RuntimeError(""",
    ),
]


def run_tests() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-q", "--no-header", "-x"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0, (proc.stdout or "")[-400:]


def main() -> int:
    ok, _ = run_tests()
    if not ok:
        print("BASELINE FAILING - fix the suite before mutating")
        return 1
    print("baseline: PASS\n")

    survived: list[str] = []
    for name, path, original, replacement in MUTATIONS:
        src = path.read_text(encoding="utf-8")
        if original not in src:
            print(f"SKIP  {name}\n      (anchor not found - mutation is stale)")
            survived.append(f"{name} [stale anchor]")
            continue
        path.write_text(src.replace(original, replacement, 1), encoding="utf-8")
        try:
            passed, tail = run_tests()
        finally:
            path.write_text(src, encoding="utf-8")
        if passed:
            print(f"SURVIVED  {name}\n          -> no test catches this")
            survived.append(name)
        else:
            print(f"caught    {name}")

    print()
    if survived:
        print(f"{len(survived)} of {len(MUTATIONS)} mutations SURVIVED:")
        for s in survived:
            print(f"  - {s}")
        return 1
    print(f"all {len(MUTATIONS)} mutations caught")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
