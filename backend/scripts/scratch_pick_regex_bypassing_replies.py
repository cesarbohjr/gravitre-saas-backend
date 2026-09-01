"""Which candidate replies genuinely bypass the regex fast path?

A live test of site 5 only exercises the model call if the regex cannot classify
the reply. Anything the fast path already handles proves nothing about the fix.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import dotenv_values

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

for p in (ROOT / "backend" / ".env", ROOT / ".env"):
    if p.is_file():
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                for k, v in dotenv_values(p, encoding=enc).items():
                    if v:
                        os.environ.setdefault(k, v)
                break
            except UnicodeDecodeError:
                continue

from app.services.pending_reply_classifier import (  # noqa: E402
    build_pending_snapshot,
    classify_pending_reply_fast,
)

STATE = {
    "pending_task": {
        "status": "awaiting_confirm",
        "invoke_action": "hubspot.lists.create",
        "action_label": "Create list via HubSpot",
        "params": {
            "status": "awaiting_confirm",
            "invoke_action": "hubspot.lists.create",
            "args": {"name": "Q4 Renewals", "object_type_id": "0-1"},
        },
    }
}

CANDIDATES = [
    "hold off on that for now, I want to check the numbers with finance first",
    "let me run that past finance before we commit to it",
    "what exactly is that going to do to our existing lists?",
    "actually I'd rather it covered Q1 instead",
    "yes",
    "cancel",
    "not yet, the board meeting is Thursday and I want their read first",
]


def main() -> int:
    snap = build_pending_snapshot(STATE)
    print(f"pending recognised: status={snap.status!r} action={snap.invoke_action!r}\n")
    for msg in CANDIDATES:
        fast = classify_pending_reply_fast(msg, snap)
        verdict = "NEEDS MODEL" if fast is None else f"regex -> {fast}"
        print(f"  [{verdict:16}] {msg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
