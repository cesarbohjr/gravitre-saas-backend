"""Probe: the five Google entity_get actions the adapter used to reject.

The executability gate checked raw registry membership while invoke_tool resolves
aliases first, so these were reported read_action_not_registered even though the
read executes. Confirms the resolved read really is dispatched.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

sys.stdout.reconfigure(encoding="utf-8")

from app.services.entity_get_verify import verify_entity_get  # noqa: E402

ACTIONS = [
    "google_drive.files.create",
    "google_drive.files.update",
    "google_docs.documents.create",
    "google_sheets.spreadsheets.create",
    "google_sheets.values.update",
]


def main() -> int:
    ctx = MagicMock()
    ctx.connector_id = "conn-1"
    seen: list[str] = []

    def fake_invoke(_ctx, action, params):
        shown = {k: v for k, v in params.items() if k != "connector_id"}
        seen.append(f"{action} {shown}")
        out = MagicMock()
        out.success = True
        out.data = {"id": "FILE123"}
        return out

    failures = 0
    for act in ACTIONS:
        seen.clear()
        with patch("app.services.tool_service.invoke_tool", fake_invoke):
            r = verify_entity_get(
                invoke_action=act, result_data={"id": "FILE123"}, ctx=ctx, settle=False
            )
        print(f"{act:34s} verified={r.verified} effect={r.effect} detail={r.detail}")
        print(f"    read dispatched: {seen[0] if seen else '<none>'}")
        if not r.verified:
            failures += 1

    print()
    print("RESULT:", "PASS" if failures == 0 else f"FAIL ({failures} unverified)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
