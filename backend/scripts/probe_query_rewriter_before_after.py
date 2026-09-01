"""Site 7 (query_rewriter): before/after proof the call is no longer dormant.

`rewrite_for_retrieval` turns a context-dependent follow-up ("and what about
their renewal?") into a standalone retrieval query. Its one production caller,
`agent_intelligence.py:2610`, passes the result straight into
`prepare_assistant_turn(query=refined_query)`, so it is THE query the whole
turn retrieves against.

While dormant, `get_model_router(settings)` raised TypeError before the router
ran, the handler swallowed it at WARNING, and the function returned
`refined_query == original_query`. Retrieval therefore searched on the raw
pronoun for every context-dependent follow-up in every non-fast mode.

Unlike sites 4-6 this one's failure is directly observable in its return value,
not only in control flow, so both are measured:
  1. dormancy — router entered, and what the swallowing handler logged.
  2. the degradation — refined_query identical to the original, deterministically.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
SRC = ROOT / "backend" / "app" / "services" / "query_rewriter.py"
OUT = ROOT / "docs" / "delivery" / "query-rewriter-before-after.json"

FIXED = "        router = get_model_router()"
BUGGY = "        router = get_model_router(settings)"

# A follow-up that is meaningless without the conversation: "their" has no
# referent in the string itself, so retrieving on it as-is cannot work.
QUERY = "and what about their renewal?"
HISTORY = [
    {"role": "user", "content": "Tell me about the Acme Corp account"},
    {"role": "assistant", "content": "Acme Corp is an enterprise customer on the Platinum plan."},
]


class Capture(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[tuple[str, str]] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append((record.levelname, record.getMessage()))


def load_env() -> None:
    for p in (ROOT / "backend" / ".env", ROOT / ".env"):
        if not p.is_file():
            continue
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue


async def run_once(label: str) -> dict:
    for mod in [
        m for m in list(sys.modules) if "query_rewriter" in m or "model_router" in m
    ]:
        del sys.modules[mod]

    cap = Capture()
    root = logging.getLogger()
    root.addHandler(cap)
    root.setLevel(logging.DEBUG)

    from app.config import get_settings
    from app.services.query_rewriter import rewrite_for_retrieval

    try:
        # settings is passed exactly as the production caller passes it.
        result = await rewrite_for_retrieval(
            QUERY, HISTORY, org_id="probe-org", settings=get_settings()
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        result = {}
        error = f"{type(exc).__name__}: {exc}"

    root.removeHandler(cap)
    msgs = [f"{lv}: {m}" for lv, m in cap.records]
    entered = any("MODEL_CALL_START" in m for m in msgs)
    type_error = any("TypeError" in m or "positional argument" in m for m in msgs)
    swallowed = [m for m in msgs if "query rewrite skipped" in m]
    unchanged = result.get("refined_query") == result.get("original_query")

    print(f"\n=== {label} ===")
    print(f"  router entered (MODEL_CALL_START): {entered}")
    print(f"  TypeError seen:                    {type_error}")
    print(f"  original_query:                    {result.get('original_query')!r}")
    print(f"  refined_query:                     {result.get('refined_query')!r}")
    print(f"  returned the query unrewritten:    {unchanged}")
    for m in swallowed:
        print(f"  swallowing handler logged: {m[:170]}")
    if not swallowed:
        print("  swallowing handler logged: <nothing>")

    return {
        "label": label,
        "router_entered": entered,
        "type_error_seen": type_error,
        "result": result,
        "returned_unrewritten": unchanged,
        "handler_logged": swallowed,
        "raised": error,
    }


async def main() -> int:
    load_env()
    original = SRC.read_text(encoding="utf-8")
    if FIXED not in original:
        print("fixed call site not found — is the fix applied?")
        return 1

    results = []
    try:
        SRC.write_text(original.replace(FIXED, BUGGY, 1), encoding="utf-8")
        results.append(await run_once("BEFORE — original buggy call restored"))
        SRC.write_text(original, encoding="utf-8")
        results.append(await run_once("AFTER — fix in place"))
    finally:
        SRC.write_text(original, encoding="utf-8")

    before, after = results
    print("\n=== VERDICT ===")
    dormant_before = (
        not before["router_entered"]
        and before["type_error_seen"]
        and before["returned_unrewritten"]
    )
    live_after = after["router_entered"] and not after["type_error_seen"]
    print(f"  before: dormant (router never entered, TypeError swallowed, query unrewritten) = {dormant_before}")
    print(f"  after:  live (router entered, no TypeError) = {live_after}")

    verdict = "PASS" if dormant_before and live_after else "INCONCLUSIVE"
    if verdict == "PASS":
        print("\nPASS — site 7's dormant-call defect is closed. The rewriter now reaches")
        print("the model router; before the fix it could not, and every context-dependent")
        print("follow-up went to retrieval as its own raw, unresolved text.")
    else:
        print(f"\n{verdict} — before/after did not separate cleanly.")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "site": "backend/app/services/query_rewriter.py:52",
                "query": QUERY,
                "history": HISTORY,
                "before": before,
                "after": after,
                "verdict": verdict,
                "scope_note": (
                    "Proves the call is no longer dormant. Whether the model then "
                    "produces a GOOD standalone query needs AI provider credentials, "
                    "which this environment does not have — production only. Note "
                    "that 'refined == original' is the correct fallback on failure, "
                    "so after the fix it still looks unrewritten locally; the "
                    "discriminator is router entry, not the returned string."
                ),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"\nwrote {OUT}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
