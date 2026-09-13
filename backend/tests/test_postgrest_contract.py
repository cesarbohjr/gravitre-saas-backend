"""Standing CI gate for the postgrest-py v2 call-contract bug class.

Why this test exists (not just a one-time cleanup): the backend's unit tests
mock the Supabase client with ``unittest.mock.MagicMock``, which silently
accepts ANY attribute or method access — including ones that don't exist on
the real ``postgrest-py`` v2 library. That made two real, previously-shipped,
production-breaking bug classes completely invisible to the existing test
suite:

  1. Chaining ``.select()`` / ``.limit()`` / ``.single()`` onto the result of
     ``.insert()`` / ``.update()`` / ``.upsert()`` / ``.delete()`` — none of
     those return a builder with those methods (see
     ``backend/scripts/postgrest_contract_scan.py`` for the verified type
     contract). This first surfaced as a production HTTP 500 on
     "Create Organization" and was traced to 13 call sites; a second, more
     careful pass (recursing the whole chain instead of only the first
     chained call, and including ``.delete()``) found 6 more.
  2. Reading ``.error`` directly off a ``.execute()`` response. postgrest-py
     v2's ``APIResponse`` has only ``data``/``count`` — no ``.error``. Use
     ``app.core.supabase_response.response_error()`` instead. Found across
     98 call sites in 6 files (auth.py, connectors.py, lite.py, search.py,
     sso.py, agent_finetune_service.py) on 2026-09-12.

Both classes raise ``AttributeError`` at runtime, which ``app.main``'s global
exception handler turns into an opaque HTTP 500 with no indication of the
real cause — and MagicMock-based tests pass either way, because a mock
happily returns another mock for any attribute you ask it for.

This test runs the real AST scanner (not a mock-friendly approximation) over
every file in ``app/`` on every CI run (see ``.github/workflows/ci.yml``'s
``backend`` job, which runs `python -m pytest -q` from `backend/`), so a
*future* call site reintroducing either bug fails CI immediately instead of
shipping silently. Do not delete or weaken this test to make a new call site
pass — fix the call site, or extend the scanner's verified type contract if
the library version genuinely changed (re-verify via
``dir(postgrest._sync.request_builder.Sync...RequestBuilder)`` first).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Load by explicit file path rather than `from scripts.postgrest_contract_scan
# import ...`: the repo root also has a `scripts/` package (Node/lint
# tooling), and when the repo root precedes `backend/` on sys.path (as it
# does under some invocation orders), `import scripts` silently resolves to
# the wrong package instead of raising — a normal import would then either
# fail with a confusing AttributeError or, worse, resolve to a same-named but
# different module. Loading this specific file by path sidesteps the
# ambiguity entirely.
_SCAN_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "postgrest_contract_scan.py"
_spec = importlib.util.spec_from_file_location("_postgrest_contract_scan_gate", _SCAN_MODULE_PATH)
assert _spec and _spec.loader
_postgrest_contract_scan = importlib.util.module_from_spec(_spec)
# Register before exec: @dataclass introspects sys.modules[cls.__module__].
sys.modules[_spec.name] = _postgrest_contract_scan
_spec.loader.exec_module(_postgrest_contract_scan)
scan_backend = _postgrest_contract_scan.scan_backend


def test_no_postgrest_call_contract_violations() -> None:
    result = scan_backend()
    if not result.violations:
        return
    lines = [
        f"  {v.path}:{v.lineno} [{v.kind}] {v.detail}" for v in result.violations
    ]
    raise AssertionError(
        f"{len(result.violations)} postgrest-py v2 call-contract violation(s) "
        "found (see backend/scripts/postgrest_contract_scan.py docstring for "
        "why this is a hard gate, not a lint warning):\n" + "\n".join(lines)
    )
