"""Before/after proof that schema_param_extractor's model call is no longer dormant.

The dormancy claim was specific: `get_model_router(settings or get_settings())`
raised TypeError on every invocation and the surrounding handler swallowed it, so
the call never reached the router. That claim is decidable without any AI
provider credentials — it is about whether the router is entered at all.

This runs the real extractor twice on the same input: once with the original
buggy call restored, once with the fix in place, and compares whether the router
was entered and what the swallowing handler logged.
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
SRC = ROOT / "backend" / "app" / "services" / "schema_param_extractor.py"
OUT = ROOT / "docs" / "delivery" / "schema-param-extractor-before-after.json"

FIXED = "        response = await get_model_router().complete("
BUGGY = "        response = await get_model_router(settings or get_settings()).complete("

ACTION = "hubspot.contacts.create"
# Deliberately vague: leaves a required field empty so the extractor does not
# short-circuit before the model call. A message carrying an email address fills
# everything heuristically and never reaches the router at all.
MESSAGE = (
    "Please go ahead and set that up for the account we discussed on the call "
    "earlier this week, the usual arrangement, thanks."
)


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
    """Import fresh and run the extractor, capturing what the router path logged."""
    for mod in [m for m in list(sys.modules) if "schema_param_extractor" in m or "model_router" in m]:
        del sys.modules[mod]

    cap = Capture()
    root = logging.getLogger()
    root.addHandler(cap)
    root.setLevel(logging.DEBUG)

    from app.services.schema_param_extractor import extract_action_args

    try:
        args = await extract_action_args(ACTION, MESSAGE, use_model=True)
        error = None
    except Exception as exc:  # noqa: BLE001
        args = {}
        error = f"{type(exc).__name__}: {exc}"

    root.removeHandler(cap)
    msgs = [f"{lv}: {m}" for lv, m in cap.records]
    entered_router = any("MODEL_CALL_START" in m for m in msgs)
    type_error = any("TypeError" in m or "positional argument" in m for m in msgs)
    swallowed = [m for m in msgs if "model skipped" in m]

    print(f"\n=== {label} ===")
    print(f"  router entered (MODEL_CALL_START): {entered_router}")
    print(f"  TypeError seen anywhere:           {type_error}")
    print(f"  raised out of extractor:           {error}")
    for m in swallowed:
        print(f"  swallowing handler logged: {m[:170]}")
    if not swallowed:
        print("  swallowing handler logged: <nothing>")

    return {
        "label": label,
        "router_entered": entered_router,
        "type_error_seen": type_error,
        "raised": error,
        "handler_logged": swallowed,
        "args": args,
    }


async def main() -> int:
    load_env()
    original = SRC.read_text(encoding="utf-8")
    if FIXED not in original:
        print("fixed call site not found — is the fix still applied?")
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
    dormant_before = not before["router_entered"] and before["type_error_seen"]
    live_after = after["router_entered"] and not after["type_error_seen"]
    print(f"  before: dormant (router never entered, TypeError swallowed) = {dormant_before}")
    print(f"  after:  live (router entered, no TypeError)                 = {live_after}")
    verdict = "PASS" if dormant_before and live_after else "INCONCLUSIVE"
    if verdict == "PASS":
        print("\nPASS — the dormant-call defect at this site is closed. The call now")
        print("reaches the model router on a real invocation; before the fix it could")
        print("not, and the failure was invisible.")
    else:
        print(f"\n{verdict} — before/after did not separate cleanly.")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "site": "backend/app/services/schema_param_extractor.py — extract_action_args",
                "action": ACTION,
                "message": MESSAGE,
                "before": before,
                "after": after,
                "verdict": verdict,
                "scope_note": (
                    "Proves the call is no longer dormant. Whether the model then "
                    "contributes arguments cannot be measured locally: no AI provider "
                    "credentials are configured in this environment."
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
