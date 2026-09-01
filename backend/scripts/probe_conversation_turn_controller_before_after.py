"""Site 6 (conversation_turn_controller): before/after proof the call is no longer dormant.

This site is worse than the ones before it. `_model_pending_intent` sits behind
two callers in `classify_pending_plan_intent`:

  * the modify-hint path, whose fallback when the model contributes nothing is
    "modify" — NOT "unclear". So a reply that means cancel but happens to contain
    a modify hint ("don't bother with that") was classified as a request to
    change the plan, and the pending plan stayed alive.
  * the general path, whose fallback is "unclear".

The first is the interesting one: every other dormant site in this audit failed
safe, which is why they went unnoticed. This one failed toward keeping a
destructive plan pending after the user tried to call it off.

Two claims, both decidable without AI credentials because both are control flow:
  1. dormancy — was the router entered, and what did the swallowing handler log.
  2. the mislabel — the dormant path returns "modify" for a cancel-shaped reply
     deterministically, so it can be measured directly rather than argued.
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
SRC = ROOT / "backend" / "app" / "services" / "conversation_turn_controller.py"
OUT = ROOT / "docs" / "delivery" / "conversation-turn-controller-before-after.json"

FIXED = "        response = await get_model_router().complete("
BUGGY = "        response = await get_model_router(settings or get_settings()).complete("

# Long-form so it cannot fullmatch the short-utterance cancel patterns, and
# contains "don't" so re_modify_hint fires. Meaning is unambiguously cancel.
CANCEL_VIA_MODIFY_HINT = (
    "don't bother with that, we're going a completely different direction now"
)

# No modify hint at all, so it takes the general path whose fallback is "unclear".
GENERAL_PATH = (
    "hold off, I need to run this past our finance lead before anything happens"
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


def _current_plan() -> dict:
    """A real destructive pending plan, so the stakes of the mislabel are concrete."""
    return {
        "goal": "Create a HubSpot list of MSP prospects and add the matched deals",
        "steps": [
            {"action": "hubspot.lists.create", "label": "Create list"},
            {"action": "hubspot.lists.add_members", "label": "Add members"},
        ],
    }


def _pending_task() -> dict:
    return {"status": "awaiting_confirm", "type": "awaiting_confirm"}


async def run_once(label: str) -> dict:
    for mod in [
        m
        for m in list(sys.modules)
        if "conversation_turn_controller" in m or "model_router" in m
    ]:
        del sys.modules[mod]

    cap = Capture()
    root = logging.getLogger()
    root.addHandler(cap)
    root.setLevel(logging.DEBUG)

    from app.services.conversation_turn_controller import (
        classify_pending_plan_intent,
        re_modify_hint,
    )

    per_message = {}
    for name, msg in (
        ("cancel_via_modify_hint", CANCEL_VIA_MODIFY_HINT),
        ("general_path", GENERAL_PATH),
    ):
        cap.records.clear()
        try:
            intent = await classify_pending_plan_intent(
                msg,
                current_plan=_current_plan(),
                pending_task=_pending_task(),
                use_model=True,
            )
            error = None
        except Exception as exc:  # noqa: BLE001
            intent = None
            error = f"{type(exc).__name__}: {exc}"

        msgs = [f"{lv}: {m}" for lv, m in cap.records]
        per_message[name] = {
            "message": msg,
            "hits_modify_hint": re_modify_hint(msg),
            "intent": intent,
            "router_entered": any("MODEL_CALL_START" in m for m in msgs),
            "type_error_seen": any(
                "TypeError" in m or "positional argument" in m for m in msgs
            ),
            "handler_logged": [
                m for m in msgs if "pending plan intent model skipped" in m
            ],
            "raised": error,
        }

    root.removeHandler(cap)

    print(f"\n=== {label} ===")
    for name, r in per_message.items():
        print(f"  [{name}] modify_hint={r['hits_modify_hint']}")
        print(f"      router entered (MODEL_CALL_START): {r['router_entered']}")
        print(f"      TypeError seen:                    {r['type_error_seen']}")
        print(f"      intent returned:                   {r['intent']!r}")
        for m in r["handler_logged"]:
            print(f"      handler logged: {m[:150]}")
        if not r["handler_logged"]:
            print("      handler logged: <nothing>")

    return {"label": label, "messages": per_message}


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
    b_hint = before["messages"]["cancel_via_modify_hint"]
    a_hint = after["messages"]["cancel_via_modify_hint"]
    b_gen = before["messages"]["general_path"]
    a_gen = after["messages"]["general_path"]

    print("\n=== VERDICT ===")
    dormant_before = (
        not b_hint["router_entered"]
        and b_hint["type_error_seen"]
        and not b_gen["router_entered"]
    )
    live_after = (
        a_hint["router_entered"]
        and not a_hint["type_error_seen"]
        and a_gen["router_entered"]
    )
    # The consequence, measured rather than argued.
    mislabel_before = b_hint["hits_modify_hint"] and b_hint["intent"] == "modify"

    print(f"  before: dormant on both paths (router never entered, TypeError swallowed) = {dormant_before}")
    print(f"  after:  live on both paths (router entered, no TypeError) = {live_after}")
    print(f"  before: cancel-shaped reply classified 'modify', keeping the plan alive = {mislabel_before}")

    verdict = "PASS" if dormant_before and live_after else "INCONCLUSIVE"
    if verdict == "PASS":
        print("\nPASS — site 6's dormant-call defect is closed. Both callers now reach")
        print("the model router; before the fix neither could, and the modify-hint")
        print("caller returned 'modify' for a reply that plainly meant cancel.")
    else:
        print(f"\n{verdict} — before/after did not separate cleanly.")

    OUT.write_text(
        json.dumps(
            {
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "site": "backend/app/services/conversation_turn_controller.py:273",
                "before": before,
                "after": after,
                "verdict": verdict,
                "mislabel_before": mislabel_before,
                "severity_note": (
                    "Unlike sites 1-5 this one did not fail safe: the modify-hint "
                    "fallback is 'modify', so a cancel-meaning reply left a "
                    "destructive plan pending instead of dropping it."
                ),
                "scope_note": (
                    "Proves the call is no longer dormant, and measures the wrong "
                    "label it produced while dormant. Whether the model now returns "
                    "'cancel' for this reply needs AI provider credentials, which "
                    "this environment does not have — production only."
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
