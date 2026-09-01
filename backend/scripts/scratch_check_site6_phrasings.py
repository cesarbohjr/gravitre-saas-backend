"""Negative control for site 6's live proof.

The live PASS rests on the general-path branch being unable to return
cancel/modify/continue without the model. That only holds if the regex fast
paths ahead of it decline these phrasings. Verify rather than assume.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.conversation_turn_controller import re_modify_hint  # noqa: E402
from app.services.conversational_execution_service import CONFIRM_PATTERN  # noqa: E402
from app.services.pending_reply_classifier import is_clear_pending_cancel_intent  # noqa: E402

MSGS = [
    "hold off, I need to run this past our finance lead before anything happens",
    "don't bother with that, we're going a completely different direction now",
]

for m in MSGS:
    cancel = is_clear_pending_cancel_intent(m)
    confirm = bool(CONFIRM_PATTERN.match(m)) or m.lower() in {
        "yes",
        "y",
        "ok",
        "okay",
        "confirm",
    }
    hint = re_modify_hint(m)
    if hint:
        branch = "modify-hint branch (fallback 'modify')"
    elif not cancel and not confirm:
        branch = "general branch (fallback 'unclear')"
    else:
        branch = "regex fast path — model NOT needed"
    print(f"{m!r}")
    print(f"   clear-cancel regex : {cancel}")
    print(f"   confirm regex      : {confirm}")
    print(f"   modify hint        : {hint}")
    print(f"   -> {branch}\n")

decided_by_regex = [
    m
    for m in MSGS
    if is_clear_pending_cancel_intent(m)
    or bool(CONFIRM_PATTERN.match(m))
    or m.lower() in {"yes", "y", "ok", "okay", "confirm"}
]
if decided_by_regex:
    print("FAIL — a probe phrasing is decided by regex; the live proof would be vacuous:")
    for m in decided_by_regex:
        print(f"  {m!r}")
    raise SystemExit(1)
print("OK — neither phrasing is decided by regex, so the model is the only route")
print("to a non-fallback label. The live result is not explainable by the fast path.")
