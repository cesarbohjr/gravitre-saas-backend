"""Site 5 (pending_reply_classifier): before/after proof the call is no longer dormant.

While dormant, `_model_pending_reply_intent` raised TypeError before reaching the
router and the handler swallowed it, so every reply the regex fast path could not
classify returned "ambiguous". The assistant then re-asked instead of reading the
conversation. It failed safe, which is why it went unnoticed.

The claim is about control flow, so it is decidable without AI credentials: did
the router get entered, and what did the swallowing handler log. This runs the
real classifier twice on the same input, once with the original buggy call
restored.
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
SRC = ROOT / "backend" / "app" / "services" / "pending_reply_classifier.py"
OUT = ROOT / "docs" / "delivery" / "pending-reply-classifier-before-after.json"

FIXED = "        response = await get_model_router().complete("
BUGGY = "        response = await get_model_router(settings or get_settings()).complete("

# Deliberately past the regex fast path: no bare yes/no, no cancel word, no
# field value. Comprehension is the only way to classify it correctly, so this
# is exactly the reply that was silently degraded to "ambiguous".
MESSAGE = "hold off on that for now, I want to check the numbers with finance first"


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


def _pending_state() -> dict:
    """A real awaiting_confirm hold, matching the shape production persists."""
    return {
        "pending_task": {
            "status": "awaiting_confirm",
            "invoke_action": "hubspot.deals.update",
            "action_label": "Update deal stage via HubSpot",
            "params": {
                "status": "awaiting_confirm",
                "invoke_action": "hubspot.deals.update",
                "args": {"deal_id": "222860683241", "dealstage": "closedwon"},
            },
        }
    }


async def run_once(label: str) -> dict:
    for mod in [
        m
        for m in list(sys.modules)
        if "pending_reply_classifier" in m or "model_router" in m
    ]:
        del sys.modules[mod]

    cap = Capture()
    root = logging.getLogger()
    root.addHandler(cap)
    root.setLevel(logging.DEBUG)

    from app.services.pending_reply_classifier import (
        classify_pending_reply_fast,
        classify_pending_reply,
        build_pending_snapshot,
    )

    state = _pending_state()
    snap = build_pending_snapshot(state)
    fast = classify_pending_reply_fast(MESSAGE, snap)

    try:
        intent = await classify_pending_reply(
            MESSAGE,
            task_state=state,
            use_model=True,
            conversation_turns=[
                {"role": "user", "content": "move the Acme deal to closed won"},
                {"role": "assistant", "content": "I'm waiting for your approval to run Update deal stage."},
            ],
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        intent = None
        error = f"{type(exc).__name__}: {exc}"

    root.removeHandler(cap)
    msgs = [f"{lv}: {m}" for lv, m in cap.records]
    entered_router = any("MODEL_CALL_START" in m for m in msgs)
    type_error = any("TypeError" in m or "positional argument" in m for m in msgs)
    swallowed = [m for m in msgs if "pending_reply model classify skipped" in m]

    print(f"\n=== {label} ===")
    print(f"  regex fast path result:            {fast!r} (None means model needed)")
    print(f"  router entered (MODEL_CALL_START): {entered_router}")
    print(f"  TypeError seen anywhere:           {type_error}")
    print(f"  final intent returned:             {intent!r}")
    for m in swallowed:
        print(f"  swallowing handler logged: {m[:170]}")
    if not swallowed:
        print("  swallowing handler logged: <nothing>")

    return {
        "label": label,
        "regex_fast_path": fast,
        "router_entered": entered_router,
        "type_error_seen": type_error,
        "intent": intent,
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
    needed_model = before["regex_fast_path"] is None
    dormant_before = needed_model and not before["router_entered"] and before["type_error_seen"]
    live_after = after["router_entered"] and not after["type_error_seen"]
    print(f"  reply genuinely needs the model (regex returned None) = {needed_model}")
    print(f"  before: dormant (router never entered, TypeError swallowed) = {dormant_before}")
    print(f"  after:  live (router entered, no TypeError) = {live_after}")

    verdict = "PASS" if dormant_before and live_after else "INCONCLUSIVE"
    if verdict == "PASS":
        print("\nPASS — site 5's dormant-call defect is closed. On a reply the regex")
        print("cannot classify, the classifier now reaches the model router; before")
        print("the fix it could not, and returned 'ambiguous' with no error surfaced.")
    else:
        print(f"\n{verdict} — before/after did not separate cleanly.")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "site": "backend/app/services/pending_reply_classifier.py:500",
                "message": MESSAGE,
                "before": before,
                "after": after,
                "verdict": verdict,
                "scope_note": (
                    "Proves the call is no longer dormant. Whether the model then "
                    "classifies this reply correctly needs AI provider credentials, "
                    "which this environment does not have — production only."
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
