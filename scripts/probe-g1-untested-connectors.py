#!/usr/bin/env python3
"""G.1 untested-connector NL probe + Monday F4 sibling check."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.chat_action_mapper import ChatActionMapper

PROBES = [
    ("asana", ["asana"], "create a task in Asana called Follow up with Acme", "asana.tasks.create"),
    ("clickup", ["clickup"], "list my open ClickUp tasks", "clickup.tasks.list"),
    ("github", ["github"], "search GitHub issues mentioning billing", "github.issues.list"),
    ("notion", ["notion"], "create a Notion page titled Q3 plan", "notion.pages.create"),
    ("airtable", ["airtable"], "find records in Airtable for Acme", "airtable.records.list"),
    ("monday_item", ["monday"], "create a Monday.com item for onboarding", "monday.items.create"),
    ("monday_task", ["monday"], 'Create a task in Monday called "Follow up"', "monday.items.create"),
    # Linear has catalog specs but 0 chat_executable matrix rows today — expect MISS.
    ("linear", ["linear"], "create a Linear issue titled Fix login", None),
    ("zendesk", ["zendesk"], "list open Zendesk tickets", "zendesk.tickets.list"),
    ("salesforce", ["salesforce"], "find Salesforce contacts named Sarah", "salesforce.contacts.search"),
    # No conversations.search in matrix — list is the correct chat-executable sibling.
    ("intercom", ["intercom"], "search Intercom conversations about refund", "intercom.conversations.list"),
]

OUT = ROOT / "docs" / "delivery" / "g1-untested-connectors-probe.json"


def main() -> int:
    mapper = ChatActionMapper()
    rows = []
    for vendor, conns, msg, expected in PROBES:
        match = mapper.match_segment(msg, connected_integrations=conns)
        tool = match.entry.registry_key if match else None
        if expected is None:
            correct = match is None
        else:
            correct = tool == expected
        rows.append(
            {
                "vendor": vendor,
                "message": msg,
                "expected": expected,
                "tool": tool,
                "score": round(float(match.score), 2) if match else None,
                "correct": correct,
                "hit": match is not None,
            }
        )
        print(("PASS" if correct else "FAIL"), vendor, tool, "|", msg[:50])
    report = {
        "correct": sum(1 for r in rows if r["correct"]),
        "n": len(rows),
        "rows": rows,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"correct": report["correct"], "n": report["n"]}, indent=2))
    print("wrote", OUT)
    return 0 if report["correct"] == report["n"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
