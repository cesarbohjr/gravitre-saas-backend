"""Standing guard: no NarrowedTools value may be rebuilt into a plain list.

The narrowing proof is an attribute on a `list` subclass, so `list(x)`, a
comprehension over `x`, a slice, `sorted(x)` and `copy()` all discard it
silently. Python cannot prevent this -- `list(x)` returning a plain list is
language behaviour, not something a subclass can override. So the only real
protection is to detect the shape in CI.

This test runs `scripts/scan_narrowed_tools_strips.py` over `backend/app` and
fails on two verdicts:

  ATTACH            a stripped rebuild can reach a model attach site
  BLINDS_PRESERVER  a stripped value is passed to a function whose own
                    re-marking branch then cannot see it, making that branch
                    dead code

History: the same mistake was made three times. Two produced the 119-event
`unnarrowed_tool_attach_blocked` burst of 2026-08-12/13; the third
(`_stable_tool_list(list(visible or []))`) was found by this scan on 2026-09-02
and had silently killed that function's preserve-branch.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "scan_narrowed_tools_strips.py"


def test_no_narrowed_tools_are_stripped_on_a_path_that_matters() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0, (
        "a NarrowedTools value is rebuilt into a plain list somewhere that "
        "matters. Use narrowed_tools.openai_tools_payload() or mark_narrowed() "
        "instead of list()/a comprehension/a slice.\n\n" + proc.stdout + proc.stderr
    )


def test_the_scanner_itself_is_not_vacuous() -> None:
    """A scan that finds nothing anywhere would pass while proving nothing."""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert "preserver functions detected: ['_stable_tool_list'" in proc.stdout, (
        "the scanner no longer recognises any preserver function, so its "
        "BLINDS_PRESERVER verdict can never fire"
    )
    assert "== MEASURE: " in proc.stdout
    measured = int(proc.stdout.split("== MEASURE: ")[1].split(" ==")[0])
    assert measured > 0, (
        "the scanner tracks no narrowed values at all; it would pass on an "
        "empty codebase and is not evidence of anything"
    )
